"""Run auth/P0 regressions with fake settings and every external socket denied."""
from contextlib import ExitStack
import os
import sys
from unittest.mock import patch

import run_unit_offline as offline

sys.path.insert(0, str(offline.root.parent))

# Set before pytest imports conftest/app.settings (test modules set env too late).
os.environ.update({
    "COGNITO_REGION": "ap-southeast-1", "COGNITO_USER_POOL_ID": "ap-southeast-1_testpool",
    "COGNITO_APP_CLIENT_ID": "test-client", "LOCAL_AUTH_ENABLED": "false",
    "LEARNCLOUD_RUN_AUTH_DB_TESTS": "0",
})

if __name__ == "__main__":
    import pytest
    paths = sys.argv[1:] or [str(offline.root / "tests/unit" / name) for name in (
        "test_auth_integration.py", "test_authorization_p0.py", "test_dual_auth.py")]
    with ExitStack() as stack:
        for name in ("connect", "connect_ex", "sendto"):
            stack.enter_context(patch.object(offline.socket.socket, name, offline.deny_network))
        for name in ("getaddrinfo", "create_connection"):
            stack.enter_context(patch.object(offline.socket, name, offline.deny_network))
        stack.enter_context(patch.object(offline.socket, "socketpair", offline.internal_socketpair))
        sys.exit(pytest.main([*paths, "-q", "--tb=short", "-p", "no:cacheprovider"]))
