from app.adapters._fixtures import load_json_fixture


class MockTranscriber:
    """Mô phỏng phiên âm bằng dữ liệu transcript mẫu.

    Vai trò kiến trúc: Adapter.
    """

    def transcribe(
        self,
        media_path: str,
        language_code: str = "vi-VN",
    ) -> dict:
        """Trả transcript mẫu để mô phỏng quá trình phiên âm.

        Chỉ dùng cho phát triển và kiểm thử; không xử lý media thực tế.

        Args:
            media_path: Đường dẫn media; bộ mô phỏng không đọc tệp này.
            language_code: Mã ngôn ngữ; bộ mô phỏng không sử dụng giá trị này.

        Returns:
            Đối tượng transcript mẫu có trường segments dạng danh sách.

        Raises:
            ValueError: Dữ liệu mẫu không đúng cấu trúc yêu cầu.
            OSError: Không đọc được dữ liệu mẫu.
        """
        transcript = load_json_fixture("transcript_sample.json")
        if not isinstance(transcript, dict):
            raise ValueError(
                "Expected a JSON object in transcript_sample.json."
            )
        if not isinstance(transcript.get("segments"), list):
            raise ValueError(
                "Transcript fixture must contain a segments list."
            )
        return transcript

    def get_job_status(self, job_id: str) -> dict:
        """Trả trạng thái hoàn tất giả lập của tác vụ phiên âm.

        Args:
            job_id: Mã tác vụ phiên âm cần xem trạng thái.

        Returns:
            Đối tượng chứa status bằng COMPLETED và job_id đã nhận.
        """
        return {"status": "COMPLETED", "job_id": job_id}


if __name__ == "__main__":
    transcriber = MockTranscriber()
    transcript_data = transcriber.transcribe("dummy.mp4")
    print(len(transcript_data.get("segments", [])))
