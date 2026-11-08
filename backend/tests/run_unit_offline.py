"""Run ONLY unit tests, with fake settings and all socket connections forbidden."""
import logging
import os
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ.update({
    "DATABASE_URL": "sqlite:///:memory:",
    "JWT_SECRET_KEY": "offline-unit-test-placeholder-000000000000",
    "AWS_ACCESS_KEY_ID": "offline-test-key",
    "AWS_SECRET_ACCESS_KEY": "offline-test-secret",
    "AWS_SESSION_TOKEN": "offline-test-token",
    "AWS_CONFIG_FILE": os.devnull,
    "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
    "AWS_EC2_METADATA_DISABLED": "true",
    "AWS_REGION": "ap-southeast-1",
    "AWS_DEFAULT_REGION": "ap-southeast-1",
    "S3_BUCKET": "learncloud-videos-mentorcloud",
    "VIDEO_PIPELINE_ENABLED": "false",
    "VIDEO_PROCESSOR_BACKEND": "disabled",
    "VIDEO_AI_ENABLED": "false",
    "APP_ENV": "production",
    "COGNITO_REGION": "ap-southeast-1",
    "COGNITO_USER_POOL_ID": "ap-southeast-1_offlinetest",
    "COGNITO_APP_CLIENT_ID": "offline-test-client",
    "ALLOW_RAW_VIDEO_PLAYBACK": "false",
    "LOG_LEVEL": "WARNING",
    "LOG_FORMAT": "text",
    "LEARNCLOUD_RUN_DB_TESTS": "0",
})
for name in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_ARN",
             "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "AWS_CONTAINER_CREDENTIALS_FULL_URI"):
    os.environ.pop(name, None)


original_connect = socket.socket.connect
original_socketpair = socket.socketpair
socket_context = threading.local()


def deny_network(sock, *args, **kwargs):
    # Windows asyncio builds its internal wake-up socketpair over loopback.
    # Permit only that synchronous stdlib operation, never general loopback DB/HTTP.
    if getattr(socket_context, "creating_pair", False):
        return original_connect(sock, *args, **kwargs)
    raise AssertionError("Network access is forbidden in offline unit tests.")


def internal_socketpair(*args, **kwargs):
    socket_context.creating_pair = True
    try:
        return original_socketpair(*args, **kwargs)
    finally:
        socket_context.creating_pair = False


if __name__ == "__main__":
    with patch.object(socket.socket, "connect", deny_network), \
         patch.object(socket.socket, "connect_ex", deny_network), \
         patch.object(socket.socket, "sendto", deny_network), \
         patch.object(socket, "getaddrinfo", deny_network), \
         patch.object(socket, "create_connection", deny_network), \
         patch.object(socket, "socketpair", internal_socketpair):
        suite = unittest.defaultTestLoader.discover(str(root / "tests/unit"))
        logging.getLogger().handlers = [logging.NullHandler()]
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
