# AI Pipeline

Thư mục này chứa schema, dữ liệu mẫu và prompt phục vụ xử lý transcript bài giảng bằng AI.

## Cấu trúc và quy ước

```text
ai_pipeline/
├── schemas/
│   ├── quiz.schema.json
│   └── summary.schema.json
├── fixtures/
│   ├── transcript_sample.json
│   ├── summary_sample.json
│   └── quiz_sample.json
└── prompts/
    ├── summary.txt
    ├── key_concepts.txt
    ├── quiz_generation.txt
    └── tutor_remediation.txt
```

- `schemas/`: JSON Schema Draft-07 mô tả cấu trúc đầu ra. `summary.schema.json` yêu cầu `title`, `summary` và `key_concepts` (mỗi mục có `term`, `definition`). `quiz.schema.json` yêu cầu `questions`; mỗi câu có `question`, `options`, `correct_answer` và `explanation`.
- `fixtures/`: dữ liệu giả lập dùng khi phát triển và kiểm thử local. `transcript_sample.json` chứa mảng `segments` với `start_time`, `end_time` (giây) và `text`; `summary_sample.json` và `quiz_sample.json` là đầu ra mẫu tương ứng với schema.
- `prompts/`: chỉ dẫn cho LLM. `summary.txt` yêu cầu tạo bản tóm tắt theo schema summary; `key_concepts.txt` yêu cầu trích xuất thuật ngữ và định nghĩa; `quiz_generation.txt` yêu cầu tạo 3 câu hỏi, mỗi câu có 4 lựa chọn. Prompt dùng `{{transcript}}` làm vị trí chèn transcript. `tutor_remediation.txt` dành cho hướng dẫn remediation của tutor.

## Thử dữ liệu mock local

Chạy từ thư mục gốc repository để kiểm tra các fixture đọc được dưới dạng JSON:

```bash
python -c "import json; from pathlib import Path; p=Path('ai_pipeline/fixtures'); files=['transcript_sample.json','summary_sample.json','quiz_sample.json']; [json.loads((p/name).read_text(encoding='utf-8')) for name in files]; print('Các fixture đều là JSON hợp lệ')"
```

Để thử luồng không gọi LLM, dùng nội dung `transcript_sample.json` làm đầu vào giả lập và đọc `summary_sample.json` hoặc `quiz_sample.json` làm kết quả mock tương ứng. Có thể kiểm tra kết quả với schema bằng thư viện JSON Schema Draft-07 trong môi trường local; prompt và fixture không tự thực thi hay gọi dịch vụ AI.