"""Khai báo giao diện adapter xử lý bài giảng bằng AI."""

from abc import ABCMeta, abstractmethod


class BaseAIAdapter(metaclass=ABCMeta):
    """Định nghĩa giao diện xử lý bài giảng bằng AI.

    Vai trò kiến trúc: Adapter.
    """

    @abstractmethod
    def generate_summary(self, transcript: str) -> dict:
        """Định nghĩa thao tác tạo bản tóm tắt từ transcript.

        Args:
            transcript: Nội dung bài giảng cần xử lý bằng AI.

        Returns:
            Đối tượng tóm tắt do adapter cụ thể cung cấp.
        """
        ...

    @abstractmethod
    def generate_quiz(self, transcript: str, num_questions: int = 3) -> dict:
        """Định nghĩa thao tác tạo đề trắc nghiệm từ transcript.

        Args:
            transcript: Nội dung bài giảng cần xử lý bằng AI.
            num_questions: Số câu hỏi cần tạo hoặc lấy từ dữ liệu mẫu.

        Returns:
            Đối tượng chứa các câu hỏi do adapter cụ thể cung cấp.
        """
        ...

    @abstractmethod
    def extract_key_concepts(self, transcript: str) -> list[dict[str, str]]:
        """Định nghĩa thao tác trích xuất khái niệm từ transcript.

        Args:
            transcript: Nội dung bài giảng cần xử lý bằng AI.

        Returns:
            Danh sách thuật ngữ và định nghĩa do adapter cụ thể cung cấp.
        """
        ...
