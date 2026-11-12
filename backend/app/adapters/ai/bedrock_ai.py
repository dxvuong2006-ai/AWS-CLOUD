#Adapter AI thật trên đám mây AWS
"""Kết nối Claude 3 Haiku với pipeline kiểm tra dữ liệu hiện có."""

import json
import logging
import os
from typing import Any, Callable, TypeVar

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError, ConnectionClosedError, ConnectTimeoutError,
    CredentialRetrievalError, EndpointConnectionError, NoCredentialsError,
    PartialCredentialsError, ProxyConnectionError, ReadTimeoutError, SSLError,
)

from ai_pipeline.processors.build_key_concepts import build_key_concepts
from ai_pipeline.processors.build_quiz import build_quiz
from ai_pipeline.processors.build_summary import build_summary
from app.adapters.ai.base import BaseAIAdapter
from app.adapters.ai.mock_ai import MockAIAdapter
from app.config import settings

logger = logging.getLogger(__name__)
T = TypeVar("T")
MAX_RESPONSE_BYTES = 1_000_000
AWS_FAILURES = (
    ClientError, ConnectionClosedError, ConnectTimeoutError,
    CredentialRetrievalError, EndpointConnectionError, NoCredentialsError,
    PartialCredentialsError, ProxyConnectionError, ReadTimeoutError, SSLError,
)


class BedrockAIAdapter(BaseAIAdapter):
    """Sinh nội dung bằng Bedrock và kiểm tra hợp đồng đầu ra.

    Vai trò kiến trúc: Adapter.
    """

    def __init__(
        self, *, allow_fallback: bool = False, client: Any = None,
        model_id: str | None = None, region_name: str | None = None,
    ) -> None:
        """Khởi tạo cấu hình; chỉ tạo kết nối khi có yêu cầu.

        Args:
            allow_fallback: Cho phép dữ liệu Mock khi AWS không khả dụng.
            client: Client được tiêm để kiểm thử, không cần gọi AWS thật.
            model_id: Mã mô hình; mặc định lấy BEDROCK_MODEL_ID.
            region_name: Vùng AWS; mặc định lấy AWS_REGION hoặc us-east-1.
        """
        self.allow_fallback = allow_fallback
        self.model_id = model_id or os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-haiku-20240307-v1:0",
        )
        self.region_name = (
            region_name or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION") or settings.AWS_REGION
        )
        self._client = client
        self.used_fallback = False

    def _invoke(self, prompt: str) -> str:
        """Gọi Messages API và trả văn bản JSON chưa phân tích.

        Args:
            prompt: Chỉ dẫn đã ghép transcript.

        Returns:
            Văn bản do Claude sinh; stream luôn được đóng.
        """
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime", region_name=self.region_name,
                config=Config(
                    connect_timeout=5, read_timeout=60,
                    retries={"total_max_attempts": 2, "mode": "standard"},
                ),
            )
        response = self._client.invoke_model(
            modelId=self.model_id, contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        stream = response["body"]
        try:
            payload = stream.read(MAX_RESPONSE_BYTES + 1)
        finally:
            stream.close()
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("Claude returned an oversized response.")
        try:
            result = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Claude returned an invalid response envelope.") from None
        if not isinstance(result, dict):
            raise ValueError("Claude returned an invalid response envelope.")
        if result.get("stop_reason") == "max_tokens":
            raise ValueError("Claude response exceeded the token limit.")
        blocks = result.get("content")
        if not isinstance(blocks, list) or any(
            not isinstance(block, dict)
            or (
                block.get("type") == "text"
                and not isinstance(block.get("text"), str)
            )
            for block in blocks
        ):
            raise ValueError("Claude returned an invalid content envelope.")
        text = "".join(
            block["text"] for block in blocks if block.get("type") == "text"
        )
        if not text.strip():
            raise ValueError("Claude returned no text.")
        return text

    def _run(self, operation: Callable[[], T], fallback: Callable[[], T]) -> T:
        """Áp dụng dự phòng có khai báo cho lỗi AWS.

        Args:
            operation: Thao tác gọi AI và kiểm tra schema.
            fallback: Thao tác Mock chỉ được chạy khi đã bật cờ.

        Returns:
            Kết quả hợp lệ; không nuốt lỗi dữ liệu hay lỗi lập trình.
        """
        try:
            return operation()
        except AWS_FAILURES as exc:
            if not self.allow_fallback:
                raise
            self.used_fallback = True
            logger.warning(
                "Bedrock source=mock; reason=%s", type(exc).__name__,
            )
            return fallback()

    def generate_summary(self, transcript: str) -> dict:
        """Tạo tóm tắt đã kiểm tra schema.

        Args:
            transcript: Văn bản bài giảng không rỗng.

        Returns:
            Đối tượng title, summary và key_concepts.
        """
        return self._run(
            lambda: build_summary(
                transcript, self._invoke, allow_fallback=False,
            ),
            lambda: MockAIAdapter().generate_summary(transcript),
        )

    def generate_quiz(self, transcript: str, num_questions: int = 3) -> dict:
        """Tạo đề với số câu và đáp án hợp lệ.

        Args:
            transcript: Văn bản bài giảng.
            num_questions: Số câu hỏi cần sinh.

        Returns:
            Đối tượng questions giữ nguyên trường options.
        """
        return self._run(
            lambda: build_quiz(
                transcript, self._invoke, num_questions=num_questions,
                allow_fallback=False,
            ),
            lambda: MockAIAdapter().generate_quiz(transcript, num_questions),
        )

    def extract_key_concepts(self, transcript: str) -> list[dict[str, str]]:
        """Trích xuất danh sách khái niệm đã kiểm tra.

        Args:
            transcript: Văn bản bài giảng.

        Returns:
            Danh sách cặp term và definition.
        """
        return self._run(
            lambda: build_key_concepts(
                transcript, self._invoke, allow_fallback=False,
            ),
            lambda: MockAIAdapter().extract_key_concepts(transcript),
        )
