from app.main import app


def test_quiz_openapi_documents_runtime_error_status_codes():
    schema = app.openapi()

    get_quiz = schema["paths"]["/sections/{section_id}/quiz"]["get"]
    submit_quiz = schema["paths"]["/quizzes/{quiz_id}/attempts"]["post"]

    assert {"200", "403", "404", "422"} <= set(get_quiz["responses"])
    assert {"200", "403", "404", "409", "422"} <= set(
        submit_quiz["responses"]
    )
    assert get_quiz["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/QuizDetailResponse")
    assert submit_quiz["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/QuizAttemptResultResponse")
    request_schema = submit_quiz["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    assert request_schema.endswith("/QuizSubmitRequest")
    required = schema["components"]["schemas"]["QuizSubmitRequest"]["required"]
    assert "request_id" in required
