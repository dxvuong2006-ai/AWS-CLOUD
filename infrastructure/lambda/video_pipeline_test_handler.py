"""Dedicated K4 E2E-test entrypoint; never use as the production handler."""

from app.test_database_guard import require_k5_test_database
import video_pipeline_handler as runtime


def handler(event, context):
    require_k5_test_database()
    if (
        isinstance(event, dict)
        and event.get("source") == "aws.states"
        and event.get("detail-type") == "Step Functions Execution Status Change"
    ):
        return runtime.recovery_handler(event, context)
    return runtime.handler(event, context)
