#Adapter AI thật trên đám mây AWS
"""Kết nối Amazon Nova với pipeline kiểm tra dữ liệu hiện có."""

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

logger = logging.getLogger(__name__)
T = TypeVar("T")
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
            region_name: Vùng AWS; mặc định lấy AWS_REGION hoặc ap-southeast-1.
        """
        self.allow_fallback = allow_fallback
        self.model_id = model_id or os.getenv(
            "BEDROCK_MODEL_ID",
            "amazon.nova-micro-v1:0",
        )
        self.region_name = (
            region_name or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION") or "ap-southeast-1"
        )
        self._client = client
        self.used_fallback = False

    def _invoke(self, prompt: str) -> str:
        """Gọi Messages API và trả văn bản JSON chưa phân tích.

        Args:
            prompt: Chỉ dẫn đã ghép transcript.

        Returns:
            Văn bản do mô hình Bedrock sinh.
        """
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime", region_name=self.region_name,
                config=Config(
                    connect_timeout=5, read_timeout=60,
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )
        response = self._client.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 4096, "temperature": 0},
        )
        if response.get("stopReason") == "max_tokens":
            raise ValueError("Bedrock response exceeded the token limit.")
        output = response.get("output", {})
        blocks = output.get("message", {}).get("content")
        if not isinstance(blocks, list) or any(
            not isinstance(block, dict) or
            ("text" in block and not isinstance(block["text"], str))
            for block in blocks
        ):
            raise ValueError("Bedrock returned an invalid content envelope.")
        text = "".join(block.get("text", "") for block in blocks)
        if not text.strip():
            raise ValueError("Bedrock returned no text.")
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
