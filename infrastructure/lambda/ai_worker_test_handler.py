"""Dedicated K5 E2E-test entrypoint; never use as the production handler."""

from app.test_database_guard import require_k5_test_database
import ai_worker_handler as runtime


def handler(event, context):
    require_k5_test_database()
    return runtime.handler(event, context)
