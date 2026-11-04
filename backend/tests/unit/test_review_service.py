"""Kiểm thử duyệt bài và Bedrock bằng SQLite, không gọi AWS thật."""

import io
import json
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import (
    ClientError, EndpointConnectionError, NoCredentialsError,
)
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event

from app.adapters.ai.bedrock_ai import BedrockAIAdapter
from app.adapters.ai.mock_ai import MockAIAdapter
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz, QuizAttempt
from app.models.user import User
from app.schemas.review import (
    DraftApproval, DraftGeneration, DraftUpdate, ReviewQuestion,
)
from app.services import lesson_service, quiz_service, review_service


@pytest.fixture
def review_context(db_session, quiz_course):
    """Tạo giảng viên sở hữu, học viên đã ghi danh và bài học nháp.

    Args:
        db_session: Session SQLite độc lập.
        quiz_course: Khóa học và ba section có sẵn.

    Returns:
        Các đối tượng phục vụ kiểm thử, không gọi dịch vụ ngoài.
    """
    student, course, sections = quiz_course
    owner = User(name="Owner", email="owner@test.local", role="INSTRUCTOR")
    outsider = User(
        name="Other", email="other@test.local", role="INSTRUCTOR",
    )
    db_session.add_all([owner, outsider])
    db_session.flush()
    course.instructor_id = owner.id
    lesson = Lesson(
        section_id=sections[0].id, title="Draft", position=1, status="DRAFT",
    )
    db_session.add_all([
        lesson, Enrollment(student_id=student.id, course_id=course.id),
    ])
    db_session.commit()
    return owner, outsider, student, lesson


def make_draft(db, context):
    """Sinh bản nháp bằng adapter Mock được tiêm tường minh.

    Args:
        db: Session SQLite.
        context: Ngữ cảnh khóa học kiểm thử.

    Returns:
        DTO REVIEW_REQUIRED đã lưu.
    """
    owner, _, _, lesson = context
    return review_service.generate_draft(
        db, lesson_id=lesson.id, instructor_id=owner.id,
        payload=DraftGeneration(transcript="Cloud computing is useful."),
        ai=MockAIAdapter(),
    )


def test_generate_pending_and_hide_from_student(db_session, review_context):
    """Xác nhận cả bài học và quiz không công khai trước khi duyệt."""
    draft = make_draft(db_session, review_context)
    owner, _, student, lesson = review_context
    assert draft.status == "REVIEW_REQUIRED"
    assert not draft.quiz_approved
    assert len(draft.questions) == 3
    assert db_session.get(Lesson, lesson.id).status == "REVIEW_REQUIRED"
    with pytest.raises(lesson_service.LessonAccessDeniedError):
        lesson_service.get_lesson_for_user(
            db_session, lesson.id, user_id=student.id, user_role="STUDENT",
        )
    assert lesson_service.list_lessons_for_section(
        db_session, lesson.section_id,
        user_id=student.id, user_role="STUDENT",
    ) == []
    with pytest.raises(quiz_service.QuizNotApprovedError):
        quiz_service.get_quiz_for_student(
            db_session, section_id=lesson.section_id,
        )
    assert review_service.get_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
    ) == draft


@pytest.mark.parametrize("actor", ["outsider", "student"])
def test_wrong_actor_cannot_read_edit_or_approve(
    db_session, review_context, actor,
):
    """Chặn truy cập chéo khóa học và tài khoản không phải giảng viên."""
    draft = make_draft(db_session, review_context)
    _, outsider, student, lesson = review_context
    user_id = outsider.id if actor == "outsider" else student.id
    content = draft.model_dump(
        include={"title", "summary", "key_concepts", "quiz_title", "questions"},
    )
    operations = (
        (review_service.get_draft, {}),
        (review_service.update_draft, {"payload": DraftUpdate(
            **content, expected_revision=draft.revision,
        )}),
        (review_service.approve_draft, {"payload": DraftApproval(
            expected_revision=draft.revision,
        )}),
    )
    for operation, kwargs in operations:
        with pytest.raises(review_service.ReviewError) as exc:
            operation(
                db_session, lesson_id=lesson.id,
                instructor_id=user_id, **kwargs,
            )
        assert exc.value.status_code == 403
    assert db_session.get(Lesson, lesson.id).status == "REVIEW_REQUIRED"


def test_edit_then_explicit_approval(db_session, review_context):
    """Sửa nháp không tự duyệt; phê duyệt mới mở nội dung học viên."""
    draft = make_draft(db_session, review_context)
    owner, _, student, lesson = review_context
    content = draft.model_dump(
        include={"title", "summary", "key_concepts", "quiz_title", "questions"},
    )
    content.update(title="Revised title", summary="Revised summary")
    content["questions"][0]["question"] = "Revised question?"
    revised = review_service.update_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
        payload=DraftUpdate(**content, expected_revision=draft.revision),
    )
    assert revised.status == "REVIEW_REQUIRED"
    assert not revised.quiz_approved
    assert revised.title == "Revised title"
    assert revised.questions[0].question == "Revised question?"
    assert revised.revision != draft.revision
    with pytest.raises(review_service.ReviewError) as exc:
        review_service.approve_draft(
            db_session, lesson_id=lesson.id, instructor_id=owner.id,
            payload=DraftApproval(expected_revision=draft.revision),
        )
    assert exc.value.status_code == 409
    approved = review_service.approve_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
        payload=DraftApproval(expected_revision=revised.revision),
    )
    assert approved.status == "PUBLISHED"
    assert approved.quiz_approved
    assert lesson_service.get_lesson_for_user(
        db_session, lesson.id, user_id=student.id, user_role="STUDENT",
    ).status == "PUBLISHED"
    public = quiz_service.get_quiz_for_student(
        db_session, section_id=lesson.section_id,
    )
    assert "correct_answer" not in public["questions"][0]
    assert "explanation" not in public["questions"][0]
    visible = lesson_service.list_lessons_for_section(
        db_session, lesson.section_id, user_id=student.id,
        user_role="STUDENT", skip=0, limit=1,
    )
    assert [item.id for item in visible] == [lesson.id]


def test_quiz_waits_for_other_pending_lesson(db_session, review_context):
    """Quiz dùng chung chỉ mở khi các bài nháp trong section đã được duyệt."""
    first = make_draft(db_session, review_context)
    owner, _, _, lesson = review_context
    other = Lesson(
        section_id=lesson.section_id, title="Other pending", position=2,
        status="REVIEW_REQUIRED", summary="Summary",
        key_concepts_json=[{"term": "Cloud", "definition": "Compute"}],
    )
    db_session.add(other)
    db_session.commit()
    result = review_service.approve_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
        payload=DraftApproval(expected_revision=first.revision),
    )
    assert result.status == "PUBLISHED"
    assert not result.quiz_approved
    second = review_service.get_draft(
        db_session, lesson_id=other.id, instructor_id=owner.id,
    )
    final = review_service.approve_draft(
        db_session, lesson_id=other.id, instructor_id=owner.id,
        payload=DraftApproval(expected_revision=second.revision),
    )
    assert final.quiz_approved


def test_replacement_failure_rolls_back_all(db_session, review_context):
    """Lỗi ghi câu hỏi phải khôi phục cả summary lẫn đề cũ."""
    draft = make_draft(db_session, review_context)
    owner, _, _, lesson = review_context
    content = draft.model_dump(
        include={"title", "summary", "key_concepts", "quiz_title", "questions"},
    )
    content["summary"] = "Must roll back"

    def fail_insert(*args):
        """Mô phỏng lỗi lưu câu hỏi sau khi đã xóa đề cũ."""
        raise RuntimeError("simulated write failure")

    event.listen(Question, "before_insert", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="simulated"):
            review_service.update_draft(
                db_session, lesson_id=lesson.id, instructor_id=owner.id,
                payload=DraftUpdate(
                    **content, expected_revision=draft.revision,
                ),
            )
    finally:
        event.remove(Question, "before_insert", fail_insert)
    restored = review_service.get_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
    )
    assert restored == draft


def test_attempt_history_prevents_regeneration(db_session, review_context):
    """Không xóa hoặc thay câu hỏi đã được dùng trong lịch sử thi."""
    draft = make_draft(db_session, review_context)
    owner, _, student, lesson = review_context
    db_session.add(QuizAttempt(
        student_id=student.id, quiz_id=draft.quiz_id,
        score=100, passed=True, attempt_number=1,
    ))
    db_session.commit()
    with pytest.raises(review_service.ReviewError) as exc:
        make_draft(db_session, review_context)
    assert exc.value.status_code == 409
    assert review_service.get_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
    ) == draft


@pytest.mark.parametrize("changes", [
    {"correct_answer": "missing"},
    {"options": ["a", "a"]},
    {"question": "   "},
    {"explanation": ""},
    {"is_approved": True},
])
def test_invalid_question_rejected(changes):
    """DTO từ chối đáp án sai, chuỗi rỗng và trường ngoài hợp đồng."""
    values = dict(
        question="Question?", options=["a", "b"],
        correct_answer="a", explanation="Explanation",
    )
    with pytest.raises(ValidationError):
        ReviewQuestion(**(values | changes))


def test_ai_failure_saves_nothing(db_session, review_context):
    """Lỗi AI không để lại nội dung hoặc quiz được lưu dở."""
    owner, _, _, lesson = review_context
    ai = Mock(spec=MockAIAdapter)
    ai.generate_summary.side_effect = EndpointConnectionError(
        endpoint_url="https://bedrock.invalid",
    )
    with pytest.raises(EndpointConnectionError):
        review_service.generate_draft(
            db_session, lesson_id=lesson.id, instructor_id=owner.id,
            payload=DraftGeneration(transcript="Transcript"), ai=ai,
        )
    assert db_session.get(Lesson, lesson.id).status == "DRAFT"
    assert db_session.query(Quiz).count() == 0


def mock_response(value, *, stop_reason="end_turn"):
    """Tạo stream phản hồi Bedrock giả để kiểm tra đóng tài nguyên.

    Args:
        value: Nội dung JSON mà Claude trả.
        stop_reason: Lý do dừng mô phỏng.

    Returns:
        Stream nhị phân chứa phong bì Messages API.
    """
    return io.BytesIO(json.dumps({
        "stop_reason": stop_reason,
        "content": [{"type": "text", "text": json.dumps(value)}],
    }).encode())


@pytest.mark.parametrize("method", [
    "generate_summary", "generate_quiz", "extract_key_concepts",
])
def test_bedrock_validates_output_and_closes_stream(method):
    """Adapter gọi Haiku đúng hợp đồng và đóng stream sau khi đọc."""
    client = Mock()
    expected = getattr(MockAIAdapter(), method)("Transcript")
    stream = mock_response(expected)
    client.invoke_model.return_value = {"body": stream}
    ai = BedrockAIAdapter(client=client)
    assert getattr(ai, method)("Transcript") == expected
    assert stream.closed
    request = client.invoke_model.call_args.kwargs
    assert request["modelId"] == "anthropic.claude-3-haiku-20240307-v1:0"
    body = json.loads(request["body"])
    assert body["anthropic_version"] == "bedrock-2023-05-31"
    assert body["messages"][0]["role"] == "user"
    assert not ai.used_fallback


@pytest.mark.parametrize("error", [
    NoCredentialsError(),
    EndpointConnectionError(endpoint_url="https://bedrock.invalid"),
    ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        "InvokeModel",
    ),
])
def test_bedrock_fallback_requires_explicit_flag(error):
    """Lỗi AWS chỉ chuyển sang Mock khi có cờ cho phép."""
    client = Mock()
    client.invoke_model.side_effect = error
    strict = BedrockAIAdapter(client=client)
    with pytest.raises(type(error)):
        strict.generate_summary("Transcript")
    fallback = BedrockAIAdapter(client=client, allow_fallback=True)
    assert fallback.generate_summary("Transcript") == (
        MockAIAdapter().generate_summary("Transcript")
    )
    assert fallback.used_fallback


def test_lazy_client_env_and_missing_credentials(monkeypatch):
    """Cấu hình qua môi trường và lấy credentials bằng chuỗi mặc định."""
    monkeypatch.setenv("BEDROCK_MODEL_ID", "configured-model")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    with patch(
        "app.adapters.ai.bedrock_ai.boto3.client",
        side_effect=NoCredentialsError,
    ) as factory:
        ai = BedrockAIAdapter(allow_fallback=True)
        factory.assert_not_called()
        ai.generate_summary("Transcript")
        assert ai.used_fallback
        assert ai.model_id == "configured-model"
        assert factory.call_args.args == ("bedrock-runtime",)
        assert factory.call_args.kwargs["region_name"] == "us-west-2"
        assert "aws_access_key_id" not in factory.call_args.kwargs


@pytest.mark.parametrize("mode", ["invalid", "truncated"])
def test_invalid_ai_data_never_silently_falls_back(mode):
    """Dữ liệu sai schema hoặc bị cắt phải báo lỗi dù đã bật dự phòng."""
    stream = mock_response(
        {} if mode == "invalid" else MockAIAdapter().generate_summary("text"),
        stop_reason="max_tokens" if mode == "truncated" else "end_turn",
    )
    client = Mock()
    client.invoke_model.return_value = {"body": stream}
    ai = BedrockAIAdapter(client=client, allow_fallback=True)
    with pytest.raises(ValueError):
        ai.generate_summary("Transcript")
    assert stream.closed
    assert not ai.used_fallback


def test_review_routes_enforce_role_and_ownership(db_session, review_context):
    """API chỉ cho chủ khóa học lấy, sửa, duyệt và kiểm tra payload."""
    draft = make_draft(db_session, review_context)
    owner, outsider, student, lesson = review_context
    actor = {"user": student}

    def database_override():
        """Tiêm Session SQLite và không mở kết nối thật."""
        yield db_session

    def user_override():
        """Tiêm người dùng kiểm thử thay cho cơ chế đăng nhập."""
        return actor["user"]

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = user_override
    try:
        with TestClient(app) as client:
            url = f"/lessons/{lesson.id}/review-draft"
            assert client.get(url).status_code == 403
            actor["user"] = outsider
            assert client.get(url).status_code == 403
            actor["user"] = owner
            response = client.get(url)
            assert response.status_code == 200
            assert response.json()["revision"] == draft.revision
            assert client.put(url, json={"status": "PUBLISHED"}).status_code == 422
            response = client.post(
                url + "/approvals",
                json={"expected_revision": draft.revision},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "PUBLISHED"
    finally:
        app.dependency_overrides.clear()


def test_generation_rejects_other_owner_before_ai(db_session, review_context):
    """Từ chối giảng viên khác trước khi tiêu tốn lời gọi AI."""
    _, outsider, _, lesson = review_context
    ai = Mock(spec=MockAIAdapter)
    with pytest.raises(review_service.ReviewError) as exc:
        review_service.generate_draft(
            db_session, lesson_id=lesson.id, instructor_id=outsider.id,
            payload=DraftGeneration(transcript="Transcript"), ai=ai,
        )
    assert exc.value.status_code == 403
    ai.generate_summary.assert_not_called()


def test_missing_lesson_and_missing_draft(db_session, review_context):
    """Phân biệt tài nguyên không tồn tại và bài chưa có bản nháp."""
    owner, _, _, lesson = review_context
    with pytest.raises(review_service.ReviewError) as exc:
        review_service.get_draft(
            db_session, lesson_id=999999, instructor_id=owner.id,
        )
    assert exc.value.status_code == 404
    with pytest.raises(review_service.ReviewError) as exc:
        review_service.get_draft(
            db_session, lesson_id=lesson.id, instructor_id=owner.id,
        )
    assert exc.value.status_code == 409


def test_published_content_cannot_be_edited(db_session, review_context):
    """Không cho phép sửa trực tiếp nội dung đã được publish."""
    draft = make_draft(db_session, review_context)
    owner, _, _, lesson = review_context
    approved = review_service.approve_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
        payload=DraftApproval(expected_revision=draft.revision),
    )
    content = approved.model_dump(
        include={"title", "summary", "key_concepts", "quiz_title", "questions"},
    )
    with pytest.raises(review_service.ReviewError) as exc:
        review_service.update_draft(
            db_session, lesson_id=lesson.id, instructor_id=owner.id,
            payload=DraftUpdate(
                **content, expected_revision=approved.revision,
            ),
        )
    assert exc.value.status_code == 409


def test_mock_fallback_still_requires_review(db_session, review_context):
    """Nội dung dự phòng không thể tự chuyển thành PUBLISHED."""
    owner, _, _, lesson = review_context
    client = Mock()
    client.invoke_model.side_effect = NoCredentialsError()
    ai = BedrockAIAdapter(client=client, allow_fallback=True)
    draft = review_service.generate_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
        payload=DraftGeneration(transcript="Transcript", allow_fallback=True),
        ai=ai,
    )
    assert ai.used_fallback
    assert draft.status == "REVIEW_REQUIRED"
    assert not draft.quiz_approved


def test_approval_failure_rolls_back_status(db_session, review_context):
    """Lỗi cập nhật quiz phải rollback trạng thái publish của bài học."""
    draft = make_draft(db_session, review_context)
    owner, _, _, lesson = review_context

    def fail_update(*args):
        """Gây lỗi ghi trạng thái quiz sau khi đã flush bài học."""
        raise RuntimeError("approval write failure")

    event.listen(Quiz, "before_update", fail_update)
    try:
        with pytest.raises(RuntimeError, match="approval write failure"):
            review_service.approve_draft(
                db_session, lesson_id=lesson.id, instructor_id=owner.id,
                payload=DraftApproval(expected_revision=draft.revision),
            )
    finally:
        event.remove(Quiz, "before_update", fail_update)
    assert review_service.get_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
    ) == draft


def test_filtering_happens_before_pagination(db_session, review_context):
    """Bài chưa duyệt không chiếm chỗ của trang kết quả học viên."""
    _, _, student, lesson = review_context
    published = Lesson(
        section_id=lesson.section_id, title="Legacy published",
        position=2, status="PUBLISHED",
    )
    db_session.add(published)
    db_session.commit()
    visible = lesson_service.list_lessons_for_section(
        db_session, lesson.section_id, user_id=student.id,
        user_role="STUDENT", skip=0, limit=1,
    )
    assert [item.id for item in visible] == [published.id]


def test_postgresql_model_ddl_and_review_lock(db_session):
    """Kiểm tra sinh DDL PostgreSQL và khóa hàng mà không cần máy chủ."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable
    from app.repositories import review_repo

    ddl = str(CreateTable(Lesson.__table__).compile(
        dialect=postgresql.dialect(),
    ))
    assert "'PUBLISHED'" in ddl
    assert "JSONB" in ddl
    db = Mock()
    db.get_bind.return_value.dialect.name = "postgresql"
    review_repo.lock_section(db, lesson_id=1)
    db.query.return_value.filter.return_value.with_for_update.assert_called_once()
    review_repo.get_quiz(db, section_id=1, lock=True)
    query = db.query.return_value.filter.return_value
    query.populate_existing.return_value.with_for_update.assert_called_once()


def test_api_generate_and_update_without_aws(db_session, review_context):
    """Kiểm tra router sinh và sửa nháp bằng adapter được mock."""
    owner, _, _, lesson = review_context

    def database_override():
        """Tiêm Session kiểm thử."""
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with patch(
            "app.api.review.BedrockAIAdapter", return_value=MockAIAdapter(),
        ) as factory, TestClient(app) as client:
            response = client.post(
                f"/lessons/{lesson.id}/review-drafts",
                json={"transcript": "Transcript"},
            )
            assert response.status_code == 201
            factory.assert_called_once_with(allow_fallback=False)
            draft = response.json()
            assert draft["status"] == "REVIEW_REQUIRED"
            content = {
                key: draft[key] for key in (
                    "title", "summary", "key_concepts",
                    "quiz_title", "questions",
                )
            }
            content["title"] = "Updated through API"
            content["expected_revision"] = draft["revision"]
            result = client.put(
                f"/lessons/{lesson.id}/review-draft", json=content,
            )
            assert result.status_code == 200
            assert result.json()["title"] == "Updated through API"
            assert not result.json()["quiz_approved"]
    finally:
        app.dependency_overrides.clear()
