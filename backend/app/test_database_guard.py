"""Fail-closed database guard for dedicated K4/K5 integration-test Lambdas."""

from sqlalchemy.engine import make_url

from app.config import settings


TEST_APP_ENV = "k5-integration-test"
TEST_DATABASE_NAME = "learncloud_k5_test"
TEST_DATABASE_USER = "learncloud_k5_test_user"
POSTGRES_DRIVERS = {"postgresql", "postgresql+psycopg2"}


def require_k5_test_database() -> None:
    """Validate configuration without connecting or exposing the database URL."""
    try:
        url = make_url(settings.DATABASE_URL)
    except Exception:
        raise RuntimeError("K5_TEST_DATABASE_GUARD") from None
    if (
        settings.APP_ENV != TEST_APP_ENV
        or url.drivername not in POSTGRES_DRIVERS
        or url.username != TEST_DATABASE_USER
        or url.database != TEST_DATABASE_NAME
    ):
        raise RuntimeError("K5_TEST_DATABASE_GUARD")
