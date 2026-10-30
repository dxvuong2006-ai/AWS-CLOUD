#Adapter giả lập chạy Local / Offline
"""Cung cấp adapter AI mô phỏng từ dữ liệu mẫu cục bộ."""

from app.adapters._fixtures import load_json_fixture
from app.adapters.ai.base import BaseAIAdapter


def _load_fixture(filename: str) -> dict:
    """Đọc đối tượng JSON mẫu cho bộ mô phỏng AI.

    Args:
        filename: Tên tệp dữ liệu mẫu trong thư mục fixture.

    Returns:
        Đối tượng dữ liệu mẫu đã kiểm tra kiểu ở mức gốc.

    Raises:
        ValueError: JSON không hợp lệ hoặc dữ liệu gốc không phải object.
        OSError: Không tìm thấy hoặc không đọc được tệp mẫu.
    """
    data = load_json_fixture(filename)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in fixture: {filename}")
    return data


class MockAIAdapter(BaseAIAdapter):
    """Cung cấp dữ liệu AI mẫu cho phát triển và kiểm thử.

    Vai trò kiến trúc: Adapter.
    """

    def generate_summary(self, transcript: str) -> dict:
        """Trả bản tóm tắt mẫu phục vụ phát triển và kiểm thử.

        Không sử dụng nội dung transcript; không dùng trong production.

        Args:
            transcript: Transcript đầu vào; bộ mô phỏng bỏ qua nội dung này.

        Returns:
            Đối tượng tóm tắt cố định từ fixture.

        Raises:
            ValueError: Fixture không phải đối tượng JSON hợp lệ.
            OSError: Không đọc được fixture.
        """
        return _load_fixture("summary_sample.json")

    def generate_quiz(self, transcript: str, num_questions: int = 3) -> dict:
        """Trả số câu hỏi mẫu được yêu cầu từ fixture.

        Không sử dụng nội dung transcript; không dùng trong production.

        Args:
            transcript: Transcript đầu vào; bộ mô phỏng bỏ qua nội dung này.
            num_questions: Số câu hỏi cần tạo hoặc lấy từ dữ liệu mẫu.

        Returns:
            Đối tượng questions chứa các câu mẫu được chọn.

        Raises:
            ValueError: Số câu không hợp lệ hoặc fixture không đủ câu.
            OSError: Không đọc được fixture.
        """
        if (
            isinstance(num_questions, bool)
            or not isinstance(num_questions, int)
            or num_questions < 1
        ):
            raise ValueError("num_questions must be a positive integer.")

        quiz = _load_fixture("quiz_sample.json")
        questions = quiz.get("questions")
        if not isinstance(questions, list):
            raise ValueError("Quiz fixture must contain a questions list.")
        if num_questions > len(questions):
            raise ValueError(
                f"Requested {num_questions} questions, but the quiz fixture "
                f"contains only {len(questions)}."
            )
        return {**quiz, "questions": questions[:num_questions]}

    def extract_key_concepts(self, transcript: str) -> list[dict[str, str]]:
        """Trả danh sách khái niệm mẫu để mô phỏng AI.

        Không sử dụng nội dung transcript; không dùng trong production.

        Args:
            transcript: Transcript đầu vào; bộ mô phỏng bỏ qua nội dung này.

        Returns:
            Danh sách term/definition cố định từ fixture.

        Raises:
            ValueError: Danh sách hoặc các trường trong fixture sai kiểu.
            OSError: Không đọc được fixture.
        """
        concepts = _load_fixture("summary_sample.json").get("key_concepts")
        if not isinstance(concepts, list):
            raise ValueError(
                "Summary fixture must contain a key_concepts list."
            )
        if any(
            not isinstance(concept, dict)
            or not isinstance(concept.get("term"), str)
            or not isinstance(concept.get("definition"), str)
            for concept in concepts
        ):
            raise ValueError(
                "Each key concept fixture item must contain "
                "string term and definition."
            )
        return concepts
