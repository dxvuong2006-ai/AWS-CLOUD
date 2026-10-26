import inspect
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator


_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


class AIClientError(RuntimeError):
    """Báo lỗi nhà cung cấp AI có thể xử lý bằng cơ chế dự phòng.

    Vai trò kiến trúc: Service của AI Pipeline.
    """


def clean_text(value: Any) -> str:
    """Chuẩn hóa khoảng trắng của giá trị chuỗi.

    Args:
        value: Giá trị cần chuẩn hóa hoặc chuyển đổi.

    Returns:
        Chuỗi đã làm sạch; chuỗi rỗng nếu đầu vào không phải chuỗi.
    """
    if not isinstance(value, str):
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def split_sentences(text: str) -> list[str]:
    """Tách văn bản thành các câu đã làm sạch.

    Args:
        text: Văn bản đầu vào cần phân tích.

    Returns:
        Danh sách câu không rỗng, giữ nguyên thứ tự.
    """
    return [
        sentence
        for sentence in map(clean_text, _SENTENCE_SPLIT_RE.split(text))
        if sentence
    ]


def extract_definition_concepts(text: str) -> list[dict[str, str]]:
    """Trích xuất thuật ngữ và định nghĩa bằng quy tắc.

    Đây là trích xuất theo mẫu câu, không phải suy luận ngữ nghĩa bằng AI.

    Args:
        text: Văn bản đầu vào cần phân tích.

    Returns:
        Danh sách cặp term/definition có thuật ngữ không trùng nhau.
    """
    definition_re = re.compile(
        r"\b(?P<marker>defined\s+as|is|are)\b|"
        r"(?P<vi_marker>bao gồm|cung cấp|là|cho phép)",
        re.IGNORECASE,
    )
    leading_filler_re = re.compile(
        r"^(?:(?:mô hình|một|the|a|an)\s+)+",
        re.IGNORECASE,
    )
    concepts: list[dict[str, str]] = []
    seen_terms: set[str] = set()

    for sentence in split_sentences(text):
        match = definition_re.search(sentence)
        if match is None:
            continue

        term = leading_filler_re.sub(
            "", sentence[: match.start()].strip(" ,:;-")
        )
        words = term.split()
        if len(words) > 8:
            term = " ".join(words[-8:])
        term = term.strip(" ,:;-")
        if not term:
            continue

        marker = (match.group("marker") or match.group("vi_marker")).casefold()
        if marker == "là" and term.casefold().startswith("lợi ích"):
            term = clean_text(sentence[match.end() :].split(":", 1)[0]).rstrip(
                ".!?。！？"
            )
        normalized_term = term.casefold()
        if not normalized_term or normalized_term in seen_terms:
            continue

        seen_terms.add(normalized_term)
        concepts.append({"term": term, "definition": sentence})

    return concepts


def render_prompt(
    prompt_path: Path,
    *,
    transcript_text: str,
    replacements: dict[str, str] | None = None,
) -> str:
    """Chèn transcript và các giá trị thay thế vào chỉ dẫn AI.

    Args:
        prompt_path: Đường dẫn tệp chỉ dẫn gửi cho AI.
        transcript_text: Nội dung transcript làm nguồn xử lý bài giảng.
        replacements: Giá trị thay thế bổ sung cho các biến trong chỉ dẫn.

    Returns:
        Chuỗi chỉ dẫn đã thay thế các biến hợp lệ.

    Raises:
        ValueError: Thiếu, lặp hoặc xuất hiện biến thay thế không hỗ trợ.
        OSError: Không đọc được tệp chỉ dẫn.
    """
    template = prompt_path.read_text(encoding="utf-8")
    values = {"transcript": transcript_text, **(replacements or {})}
    placeholders = list(_PLACEHOLDER_RE.finditer(template))
    if sum(match.group(1) == "transcript" for match in placeholders) != 1:
        raise ValueError(
            "Prompt must contain exactly one {{transcript}} placeholder."
        )

    unknown = {match.group(1) for match in placeholders} - values.keys()
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Prompt contains unsupported placeholders: {names}.")

    return _PLACEHOLDER_RE.sub(
        lambda match: values[match.group(1)],
        template,
    )


def call_ai_client(
    ai_client: Any,
    *,
    prompt: str,
    transcript_text: str,
    transcript_methods: tuple[str, ...],
    transcript_method_kwargs: dict[str, Any] | None = None,
) -> Any:
    """Gọi phương thức phù hợp đầu tiên của đối tượng AI.

    Ưu tiên phương thức nhận transcript trước generate, invoke và callable.
    Chỉ truyền tham số từ khóa được hỗ trợ. Lỗi từ nhà cung cấp được ném
    lại; adapter nên chuyển lỗi có thể phục hồi thành AIClientError.

    Args:
        ai_client: Đối tượng hỗ trợ một giao diện gọi AI phù hợp.
        prompt: Chỉ dẫn đã chèn nội dung transcript.
        transcript_text: Nội dung transcript làm nguồn xử lý bài giảng.
        transcript_methods: Tên phương thức nhận transcript, theo thứ tự ưu
            tiên.
        transcript_method_kwargs: Tham số từ khóa cho phương thức nhận
            transcript.

    Returns:
        Phản hồi gốc từ phương thức đã chọn.

    Raises:
        TypeError: Đối tượng không cung cấp giao diện gọi AI phù hợp.
    """
    for method_name in transcript_methods:
        method = getattr(ai_client, method_name, None)
        if callable(method):
            kwargs = transcript_method_kwargs or {}
            if kwargs:
                try:
                    parameters = inspect.signature(method).parameters.values()
                except (TypeError, ValueError):
                    parameters = ()
                supported_kwargs = {
                    parameter.name
                    for parameter in parameters
                    if parameter.kind
                    in {
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    }
                }
                accepts_kwargs = any(
                    parameter.kind is inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters
                )
                kwargs = {
                    name: value
                    for name, value in kwargs.items()
                    if accepts_kwargs or name in supported_kwargs
                }
            else:
                kwargs = {}
            return method(transcript_text, **kwargs)

    for method_name in ("generate", "invoke"):
        method = getattr(ai_client, method_name, None)
        if callable(method):
            return method(prompt)

    if callable(ai_client):
        return ai_client(prompt)

    methods = ", ".join(
        (*transcript_methods, "generate", "invoke", "__call__")
    )
    raise TypeError(f"ai_client must provide one of: {methods}.")


def parse_json_response(response: Any) -> Any:
    """Phân tích phản hồi JSON thuần hoặc bọc trong Markdown.

    Args:
        response: Phản hồi AI cần phân tích và chuẩn hóa.

    Returns:
        Dữ liệu JSON đã giải mã; giữ nguyên đầu vào không phải chuỗi.

    Raises:
        ValueError: Chuỗi phản hồi không phải JSON hợp lệ.
    """
    if isinstance(response, (dict, list)):
        return response
    if not isinstance(response, str):
        return response

    text = response.strip()
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL
    )
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response is not valid JSON.") from exc


def validate_schema(data: Any, schema_path: Path) -> Any:
    """Kiểm tra dữ liệu theo JSON Schema Draft-07.

    Args:
        data: Dữ liệu cần thu thập hoặc kiểm tra.
        schema_path: Đường dẫn JSON Schema Draft-07 dùng kiểm tra dữ liệu.

    Returns:
        Chính dữ liệu đầu vào nếu thỏa mãn schema.

    Raises:
        ValueError: Dữ liệu không phù hợp schema hoặc tệp JSON bị lỗi.
        OSError: Không đọc được tệp schema.
        SchemaError: Định nghĩa JSON Schema không hợp lệ.
    """
    with schema_path.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    Draft7Validator.check_schema(schema)

    errors = sorted(
        Draft7Validator(schema).iter_errors(data),
        key=lambda error: (list(map(str, error.absolute_path)), error.message),
    )
    if errors:
        error = errors[0]
        location = ".".join(map(str, error.absolute_path)) or "<root>"
        raise ValueError(
            f"Output does not match {schema_path.name} at {location}: "
            f"{error.message}"
        )
    return data


def meaningful_words(text: str) -> set[str]:
    """Lấy tập từ phục vụ so khớp transcript mẫu.

    Bộ lọc dựa trên độ dài từ, không đo mức độ tương đồng ngữ nghĩa.

    Args:
        text: Văn bản đầu vào cần phân tích.

    Returns:
        Tập từ viết thường có độ dài lớn hơn ba ký tự.
    """
    return {
        word.casefold()
        for word in _WORD_RE.findall(text)
        if len(word) > 3
    }
