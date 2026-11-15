"""Fail-closed guards for the dedicated K4/K5 AWS integration-test Lambdas."""

import importlib
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.config import settings
from app.test_database_guard import require_k5_test_database


ROOT = Path(__file__).resolve().parents[3]
LAMBDA_ROOT = ROOT / "infrastructure" / "lambda"
TEST_URL = (
    "postgresql+psycopg2://learncloud_k5_test_user:placeholder@db.invalid/"
    "learncloud_k5_test"
)
FIXTURE_LESSON_ID = 4
FIXTURE_UPLOAD_ID = "00000000000000000000000000000004"
FIXTURE_RUN_ID = "65dcd70eecb600ef0ff1ec0dd3bc35c5b4444cea5668d9fd8594d689ce58eee6"


@pytest.mark.parametrize(
    ("app_env", "database_url"),
    [
        ("production", TEST_URL),
        ("k5-integration-test", "postgresql+psycopg2://user:placeholder@db.invalid/learncloud"),
        ("k5-integration-test", "postgresql+psycopg2://production_user:placeholder@db.invalid/learncloud_k5_test"),
        ("k5-integration-test", "sqlite:///learncloud_k5_test"),
        ("k5-integration-test", "not-a-database-url"),
    ],
)
def test_isolation_guard_rejects_non_test_targets(app_env, database_url):
    with (
        patch.object(settings, "APP_ENV", app_env),
        patch.object(settings, "DATABASE_URL", database_url),
        pytest.raises(RuntimeError, match="^K5_TEST_DATABASE_GUARD$"),
    ):
        require_k5_test_database()


def test_isolation_guard_accepts_only_expected_postgresql_database():
    with (
        patch.object(settings, "APP_ENV", "k5-integration-test"),
        patch.object(settings, "DATABASE_URL", TEST_URL),
    ):
        require_k5_test_database()


@pytest.mark.parametrize(
    ("module_name", "runtime_name"),
    [
        ("video_pipeline_test_handler", "video_pipeline_handler"),
        ("ai_worker_test_handler", "ai_worker_handler"),
    ],
)
def test_test_handlers_guard_before_runtime(monkeypatch, module_name, runtime_name):
    monkeypatch.syspath_prepend(str(LAMBDA_ROOT))
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    runtime = Mock()
    monkeypatch.setattr(module, "runtime", runtime)

    with (
        patch.object(settings, "APP_ENV", "production"),
        patch.object(settings, "DATABASE_URL", TEST_URL),
        pytest.raises(RuntimeError, match="^K5_TEST_DATABASE_GUARD$"),
    ):
        module.handler({}, None)

    runtime.handler.assert_not_called()


def test_k4_test_handler_routes_only_step_functions_status_events(monkeypatch):
    monkeypatch.syspath_prepend(str(LAMBDA_ROOT))
    sys.modules.pop("video_pipeline_test_handler", None)
    module = importlib.import_module("video_pipeline_test_handler")
    runtime = Mock()
    monkeypatch.setattr(module, "runtime", runtime)
    event = {
        "source": "aws.states",
        "detail-type": "Step Functions Execution Status Change",
        "detail": {"status": "FAILED"},
    }

    with (
        patch.object(settings, "APP_ENV", "k5-integration-test"),
        patch.object(settings, "DATABASE_URL", TEST_URL),
    ):
        module.handler(event, None)

    runtime.recovery_handler.assert_called_once_with(event, None)
    runtime.handler.assert_not_called()


def test_pipeline_finalize_requires_ai_flag(monkeypatch):
    monkeypatch.syspath_prepend(str(LAMBDA_ROOT))
    sys.modules.pop("video_pipeline_handler", None)
    module = importlib.import_module("video_pipeline_handler")
    finalize = Mock()
    monkeypatch.setattr(module.service, "finalize_ai", finalize)

    with (
        patch.object(settings, "VIDEO_AI_ENABLED", False),
        pytest.raises(module.service.PipelineError, match="^AI_PIPELINE_DISABLED$"),
    ):
        module._execute(
            {
                "action": "finalize_ai",
                "run_id": "a" * 64,
                "execution_arn": "arn:aws:states:ap-southeast-1:000000000000:execution:test:one",
                "proof": {"completed": True, "run_id": "a" * 64},
            },
            Mock(),
        )

    finalize.assert_not_called()


def test_fixture_run_id_matches_runtime_identity_rule():
    assert hashlib.sha256(f"{FIXTURE_UPLOAD_ID}:0".encode()).hexdigest() == FIXTURE_RUN_ID


def test_test_state_machine_is_closed_over_test_lambdas():
    definition = json.loads(
        (ROOT / "infrastructure" / "step-functions" / "k4-k5-e2e-test.asl.json").read_text()
    )
    states = definition["States"]
    transitions = set()
    function_names = set()

    for state in states.values():
        if "Next" in state:
            transitions.add(state["Next"])
        if state.get("Default"):
            transitions.add(state["Default"])
        for choice in state.get("Choices", []):
            transitions.add(choice["Next"])
        for catcher in state.get("Catch", []):
            transitions.add(catcher["Next"])
        if state.get("Resource") == "arn:aws:states:::lambda:invoke":
            function_names.add(state["Parameters"]["FunctionName"])

    assert definition["StartAt"] in states
    assert transitions <= states.keys()
    assert function_names == {"${TEST_PIPELINE_LAMBDA_ARN}", "${TEST_AI_WORKER_ARN}"}
    assert "Retry" not in states["SubmitMediaConvert"]
    assert states["AIFlagDisabled"]["Next"] == "RecordFailure"
    assert states["FinalizeAI"]["Parameters"]["Payload"]["proof.$"] == "$.proof.Payload"


def test_test_input_and_lambda_configs_are_fixture_scoped():
    step_functions = ROOT / "infrastructure" / "step-functions"
    lambda_root = ROOT / "infrastructure" / "lambda"
    event = json.loads((step_functions / "k4-k5-e2e-test-input.template.json").read_text())
    assert event == {
        "kind": "upload",
        "bucket": "learncloud-videos-mentorcloud",
        "key": "lessons/__LESSON_ID__/raw/__UPLOAD_ID__.mp4",
        "etag": "__S3_ETAG_WITHOUT_QUOTES__",
    }

    expected = {
        "k4-e2e-test-function.example.json": ("video_pipeline_test_handler.handler", "true", "false"),
        "k5-e2e-test-function.example.json": ("ai_worker_test_handler.handler", "false", "true"),
    }
    for filename, (handler, video_ai, ai_worker) in expected.items():
        config = json.loads((lambda_root / filename).read_text())
        variables = config["Environment"]["Variables"]
        assert config["FunctionName"].endswith("-k5-e2e-test")
        assert config["Handler"] == handler
        assert variables["APP_ENV"] == "k5-integration-test"
        assert "learncloud_k5_test" in variables["DATABASE_URL"]
        assert variables["VIDEO_AI_ENABLED"] == video_ai
        assert variables["AI_WORKER_ENABLED"] == ai_worker


def test_test_iam_policies_do_not_name_production_lambda_or_other_lessons():
    iam_root = ROOT / "infrastructure" / "iam"
    policy_names = [
        "k4-e2e-test-lambda-permissions.json",
        "k5-e2e-test-lambda-permissions.json",
        "k4-k5-e2e-test-step-functions-permissions.json",
        "mediaconvert-k5-e2e-test-permissions.json",
    ]
    texts = [(iam_root / name).read_text() for name in policy_names]
    for text in texts:
        json.loads(text)
        assert "learncloud-video-pipeline\"" not in text
        assert "learncloud-ai-worker\"" not in text
        assert "lessons/1/" not in text
        assert "lessons/2/" not in text

    k5_policy = json.loads(texts[1])
    resources = json.dumps(k5_policy["Statement"])
    assert FIXTURE_RUN_ID in resources
    assert f"lessons/{FIXTURE_LESSON_ID}/processed/*" in resources
    start = next(
        statement for statement in k5_policy["Statement"]
        if statement.get("Action") == "transcribe:StartTranscriptionJob"
    )
    assert start["Resource"] == "*"
    assert start["Condition"]["StringEquals"]["transcribe:OutputKey"] == (
        f"ai-transcripts/{FIXTURE_RUN_ID}/transcript.json"
    )


def test_recovery_rule_is_scoped_to_test_state_machine_placeholder():
    pattern = json.loads(
        (ROOT / "infrastructure" / "eventbridge" /
         "k4-k5-e2e-test-execution-failure.pattern.json").read_text()
    )
    assert pattern["source"] == ["aws.states"]
    assert pattern["detail"]["stateMachineArn"] == ["${TEST_STATE_MACHINE_ARN}"]
    assert set(pattern["detail"]["status"]) == {"FAILED", "TIMED_OUT", "ABORTED"}
