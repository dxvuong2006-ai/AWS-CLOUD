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

from app.adapters.ai.bedrock_ai import BedrockAIAdapter, MAX_RESPONSE_BYTES
from app.adapters.ai.mock_ai import MockAIAdapter
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.enrollment import Enrollment
from app.models.flashcard import Flashcard
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz, QuizAttempt
from app.models.section import Section
from app.models.user import User
from app.schemas.review import (
    DraftApproval, DraftGeneration, DraftUpdate, ReviewQuestion,
)
from app.services import course_service, lesson_service, quiz_service, review_service
from app.utils.errors import ConflictError, ForbiddenError

CLAUDE_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
NOVA_MODEL_ID = "apac.amazon.nova-micro-v1:0"


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
    draft = review_service.generate_draft(
        db, lesson_id=lesson.id, instructor_id=owner.id,
        payload=DraftGeneration(transcript="Cloud computing is useful."),
        ai=MockAIAdapter(),
    )
    lesson.processed_video_key = f"lessons/{lesson.id}/processed/video.mp4"
    db.commit()
    return draft


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
        include={
            "title", "summary", "key_concepts", "flashcards",
            "quiz_title", "questions",
        },
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
        include={
            "title", "summary", "key_concepts", "flashcards",
            "quiz_title", "questions",
        },
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
        processed_video_key="lessons/other/processed/video.mp4",
        transcript_json={"text": "Other transcript"},
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(Flashcard(
        lesson_id=other.id, front="Other", back="Definition", position=1,
        is_approved=False,
    ))
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
        include={"title", "summary", "key_concepts", "flashcards", "quiz_title", "questions"},
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
    ai = BedrockAIAdapter(client=client, model_id=CLAUDE_MODEL_ID)
    assert getattr(ai, method)("Transcript") == expected
    assert stream.closed
    request = client.invoke_model.call_args.kwargs
    assert request["modelId"] == CLAUDE_MODEL_ID
    body = json.loads(request["body"])
    assert body["anthropic_version"] == "bedrock-2023-05-31"
    assert body["messages"][0]["role"] == "user"
    assert not ai.used_fallback


@pytest.mark.parametrize("method", [
    "generate_summary", "generate_quiz", "extract_key_concepts",
])
def test_bedrock_nova_micro_uses_converse_contract(method):
    client = Mock()
    expected = getattr(MockAIAdapter(), method)("Transcript")
    client.converse.return_value = {
        "stopReason": "end_turn",
        "output": {"message": {
            "role": "assistant",
            "content": [{"text": json.dumps(expected)}],
        }},
    }
    ai = BedrockAIAdapter(client=client, model_id=NOVA_MODEL_ID)

    assert getattr(ai, method)("Transcript") == expected
    request = client.converse.call_args.kwargs
    assert request["modelId"] == NOVA_MODEL_ID
    assert request["inferenceConfig"] == {"maxTokens": 4096, "temperature": 0}
    assert request["messages"][0]["role"] == "user"
    assert request["messages"][0]["content"][0]["text"]
    client.invoke_model.assert_not_called()
    assert not ai.used_fallback


def test_bedrock_nova_micro_rejects_truncated_converse_response():
    client = Mock()
    client.converse.return_value = {
        "stopReason": "max_tokens",
        "output": {"message": {"content": [{"text": "{}"}]}},
    }
    ai = BedrockAIAdapter(
        client=client, model_id=NOVA_MODEL_ID, allow_fallback=True,
    )
    with pytest.raises(ValueError, match="token limit"):
        ai.generate_summary("Transcript")
    assert not ai.used_fallback


def test_bedrock_rejects_oversized_response_and_closes_stream():
    client = Mock()
    stream = io.BytesIO(b"x" * (MAX_RESPONSE_BYTES + 1))
    client.invoke_model.return_value = {"body": stream}
    with pytest.raises(ValueError, match="oversized"):
        BedrockAIAdapter(client=client, model_id=CLAUDE_MODEL_ID).generate_summary(
            "Transcript"
        )
    assert stream.closed


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
    strict = BedrockAIAdapter(client=client, model_id=CLAUDE_MODEL_ID)
    with pytest.raises(type(error)):
        strict.generate_summary("Transcript")
    fallback = BedrockAIAdapter(
        client=client, model_id=CLAUDE_MODEL_ID, allow_fallback=True,
    )
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
    ai = BedrockAIAdapter(
        client=client, model_id=CLAUDE_MODEL_ID, allow_fallback=True,
    )
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
        include={"title", "summary", "key_concepts", "flashcards", "quiz_title", "questions"},
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
    ai = BedrockAIAdapter(
        client=client, model_id=CLAUDE_MODEL_ID, allow_fallback=True,
    )
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
                    "flashcards", "quiz_title", "questions",
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


def test_manual_flashcard_and_quiz_save_reload_and_repeated_saves(
    db_session, review_context,
):
    """Manual review material survives full PUTs, commits, reloads and retries."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)

    def database_override():
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            url = f"/lessons/{lesson.id}/review-draft"
            payload = draft.model_dump(include={
                "title", "summary", "key_concepts", "flashcards",
                "quiz_title", "questions",
            })
            payload["flashcards"].append({
                "front": "Instructor card", "back": "Instructor answer",
                "position": len(payload["flashcards"]) + 1,
            })
            payload["questions"].append({
                "question": "Instructor quiz question?",
                "options": ["Correct", "Incorrect"],
                "correct_answer": "Correct", "explanation": "Verified.",
            })
            payload["expected_revision"] = draft.revision
            response = client.put(url, json=payload)
            assert response.status_code == 200, response.text
            saved = response.json()

            # Saving the same material repeatedly replaces the draft atomically;
            # it does not append duplicate rows.
            for _ in range(2):
                repeated = {**payload, "expected_revision": saved["revision"]}
                response = client.put(url, json=repeated)
                assert response.status_code == 200, response.text
                saved = response.json()

            reloaded = client.get(url)
            assert reloaded.status_code == 200
            data = reloaded.json()
            assert data["flashcards"] == saved["flashcards"]
            assert data["questions"] == saved["questions"]
            assert len(data["flashcards"]) == len(payload["flashcards"])
            assert len(data["questions"]) == len(payload["questions"])
            assert db_session.query(Flashcard).filter(
                Flashcard.lesson_id == lesson.id,
            ).count() == len(payload["flashcards"])
            assert db_session.query(Question).filter(
                Question.quiz_id == data["quiz_id"],
            ).count() == len(payload["questions"])
    finally:
        app.dependency_overrides.clear()


def test_partial_flashcard_quiz_and_summary_edits_preserve_siblings(
    db_session, review_context,
):
    """PATCH distinguishes omitted fields from explicitly replaced arrays."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)

    def database_override():
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            url = f"/lessons/{lesson.id}/ai-content"
            cards = [card.model_dump() for card in draft.flashcards]
            questions = [question.model_dump() for question in draft.questions]

            cards[0]["front"] = "Edited card only"
            result = client.patch(url, json={
                "flashcards": cards, "expected_revision": draft.revision,
            })
            assert result.status_code == 200, result.text
            draft = result.json()
            assert draft["flashcards"][0]["front"] == "Edited card only"
            assert draft["questions"] == questions

            questions[0]["question"] = "Edited quiz only?"
            result = client.patch(url, json={
                "questions": questions,
                "expected_revision": draft["revision"],
            })
            assert result.status_code == 200, result.text
            draft = result.json()
            assert draft["questions"][0]["question"] == "Edited quiz only?"
            assert draft["flashcards"][0]["front"] == "Edited card only"

            result = client.patch(url, json={
                "summary": "Summary edit only.",
                "expected_revision": draft["revision"],
            })
            assert result.status_code == 200, result.text
            assert result.json()["summary"] == "Summary edit only."
            assert result.json()["flashcards"] == draft["flashcards"]
            assert result.json()["questions"] == draft["questions"]

            # An explicit [] means delete all cards; omission above preserved them.
            result = client.patch(url, json={
                "flashcards": [],
                "expected_revision": result.json()["revision"],
            })
            assert result.status_code == 200, result.text
            assert result.json()["flashcards"] == []
            assert result.json()["questions"] == draft["questions"]
    finally:
        app.dependency_overrides.clear()


def test_full_draft_put_rejects_omitted_flashcards(
    db_session, review_context,
):
    """A missing collection is not silently interpreted as an empty collection."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)
    payload = draft.model_dump(include={
        "title", "summary", "key_concepts", "quiz_title", "questions",
    })
    payload["expected_revision"] = draft.revision

    def database_override():
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            response = client.put(
                f"/lessons/{lesson.id}/review-draft", json=payload,
            )
        assert response.status_code == 422
        assert review_service.get_draft(
            db_session, lesson_id=lesson.id, instructor_id=owner.id,
        ) == draft
    finally:
        app.dependency_overrides.clear()


def test_invalid_quiz_answer_422_keeps_draft_and_corrected_retry_saves(
    db_session, review_context,
):
    """Invalid answers are rejected without losing edits; correcting them saves."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)
    payload = draft.model_dump(include={
        "title", "summary", "key_concepts", "flashcards",
        "quiz_title", "questions",
    })
    payload["summary"] = "Instructor's unsaved summary edit."
    payload["flashcards"][0]["front"] = "Instructor's unsaved card edit."
    payload["questions"].append({
        "question": "Fourth question?", "options": ["A", "B"],
        "correct_answer": "Old option", "explanation": "Explanation.",
    })
    payload["expected_revision"] = draft.revision

    def database_override():
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            url = f"/lessons/{lesson.id}/review-draft"
            rejected = client.put(url, json=payload)
            assert rejected.status_code == 422
            assert review_service.get_draft(
                db_session, lesson_id=lesson.id, instructor_id=owner.id,
            ) == draft

            payload["questions"][3]["correct_answer"] = "A"
            accepted = client.put(url, json=payload)
            assert accepted.status_code == 200, accepted.text
            result = accepted.json()
            assert result["summary"] == "Instructor's unsaved summary edit."
            assert result["flashcards"][0]["front"] == "Instructor's unsaved card edit."
            assert result["questions"][3]["correct_answer"] == "A"
    finally:
        app.dependency_overrides.clear()


def test_ai_regeneration_cannot_overwrite_reviewed_draft(
    db_session, review_context,
):
    """A stale AI generation request cannot replace instructor-reviewed material."""
    draft = make_draft(db_session, review_context)
    owner, _, _, lesson = review_context
    content = draft.model_dump(include={
        "title", "summary", "key_concepts", "flashcards",
        "quiz_title", "questions",
    })
    content["summary"] = "Instructor's saved summary."
    edited = review_service.update_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
        payload=DraftUpdate(**content, expected_revision=draft.revision),
    )
    with pytest.raises(review_service.ReviewError) as exc:
        make_draft(db_session, review_context)
    assert exc.value.status_code == 409
    assert review_service.get_draft(
        db_session, lesson_id=lesson.id, instructor_id=owner.id,
    ) == edited


def test_patch_summary_preserves_flashcards_and_checkpoint(
    db_session, review_context,
):
    """Regression P0.4: a summary-only PATCH must not delete sibling material."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)
    before_cards = [item.model_dump() for item in draft.flashcards]
    before_concepts = [item.model_dump() for item in draft.key_concepts]
    before_questions = [item.model_dump() for item in draft.questions]

    def database_override():
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/lessons/{lesson.id}/ai-content",
                json={
                    "summary": "A revised summary only.",
                    "expected_revision": draft.revision,
                },
            )
        assert response.status_code == 200, response.text
        assert response.json()["flashcards"] == before_cards
        assert response.json()["key_concepts"] == before_concepts
        assert response.json()["questions"] == before_questions
        assert response.json()["summary"] == "A revised summary only."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda lesson, db: setattr(lesson, "processed_video_key", None), "PROCESSED_VIDEO_REQUIRED"),
        (lambda lesson, db: setattr(lesson, "transcript_json", {}), "REVIEW_CONTENT_INCOMPLETE"),
    ],
)
def test_approve_rechecks_video_ai_and_checkpoint(
    db_session, review_context, mutation, code,
):
    """Regression P0.5: approval cannot bypass persisted readiness gates."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)
    mutation(lesson, db_session)
    db_session.commit()

    with pytest.raises(ConflictError) as exc:
        review_service.approve_draft(
            db_session,
            lesson_id=lesson.id,
            instructor_id=owner.id,
            payload=DraftApproval(expected_revision=draft.revision),
        )
    assert exc.value.code == code
    assert lesson.status == "REVIEW_REQUIRED"


def test_approve_rejects_missing_checkpoint(db_session, review_context):
    """Regression P0.5: approval requires persisted checkpoint questions."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)
    quiz = review_service.review_repo.get_quiz(db_session, lesson.section_id)
    db_session.query(Question).filter(Question.quiz_id == quiz.id).delete()
    db_session.commit()

    with pytest.raises(ConflictError) as exc:
        review_service.approve_draft(
            db_session,
            lesson_id=lesson.id,
            instructor_id=owner.id,
            payload=DraftApproval(expected_revision=draft.revision),
        )
    assert exc.value.code == "CHECKPOINT_REQUIRED"
    assert lesson.status == "REVIEW_REQUIRED"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda lesson, quiz: setattr(lesson, "processed_video_key", None), "PROCESSED_VIDEO_REQUIRED"),
        (lambda lesson, quiz: setattr(lesson, "summary", ""), "REVIEW_CONTENT_INCOMPLETE"),
        (lambda lesson, quiz: setattr(quiz, "is_approved", False), "CHECKPOINT_NOT_APPROVED"),
    ],
)
def test_publish_rechecks_video_ai_and_checkpoint(
    db_session, review_context, mutation, code,
):
    """Regression P0.5: publish revalidates approved data inside its lock scope."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)
    review_service.approve_draft(
        db_session,
        lesson_id=lesson.id,
        instructor_id=owner.id,
        payload=DraftApproval(expected_revision=draft.revision),
    )
    lesson, course = review_service.review_repo.get_context(db_session, lesson.id)
    quiz = review_service.review_repo.get_quiz(db_session, lesson.section_id)
    course.status = "DRAFT"
    db_session.query(Section).filter(
        Section.course_id == course.id,
        Section.id != lesson.section_id,
    ).delete(synchronize_session=False)
    mutation(lesson, quiz)
    db_session.commit()

    with pytest.raises(ConflictError) as exc:
        course_service.publish_course(
            db_session, course.id, instructor_id=owner.id,
        )
    assert exc.value.code == code
    assert course.status == "DRAFT"


def test_publish_rechecks_owner_access(db_session, review_context):
    """Regression P0.5: a non-owner cannot publish an otherwise ready course."""
    owner, outsider, _, lesson = review_context
    _, course = review_service.review_repo.get_context(db_session, lesson.id)
    course.status = "DRAFT"
    db_session.commit()

    with pytest.raises(ForbiddenError):
        course_service.publish_course(
            db_session, course.id, instructor_id=outsider.id,
        )


def test_publish_accepts_fully_reviewed_course(db_session, review_context):
    """The P0.5 gates retain the valid approve-then-publish path."""
    owner, _, _, lesson = review_context
    draft = make_draft(db_session, review_context)
    review_service.approve_draft(
        db_session,
        lesson_id=lesson.id,
        instructor_id=owner.id,
        payload=DraftApproval(expected_revision=draft.revision),
    )
    _, course = review_service.review_repo.get_context(db_session, lesson.id)
    course.status = "DRAFT"
    db_session.query(Section).filter(
        Section.course_id == course.id,
        Section.id != lesson.section_id,
    ).delete(synchronize_session=False)
    db_session.commit()

    result = course_service.publish_course(
        db_session, course.id, instructor_id=owner.id,
    )
    assert result.status == "PUBLISHED"
