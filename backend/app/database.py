
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


DB_PASSWORD_PARAMETER_NAME = "/learncloud/db/password"


def get_lambda_db_password() -> str:
    password = os.getenv("DB_PASSWORD")
    if password:
        return password

    parameter_name = os.getenv("DB_PASSWORD_PARAMETER_NAME", DB_PASSWORD_PARAMETER_NAME)
    try:
        response = boto3.client(
            "ssm",
            region_name=os.getenv("AWS_REGION", "ap-southeast-1"),
        ).get_parameter(Name=parameter_name, WithDecryption=True)
        password = response.get("Parameter", {}).get("Value")
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(
            "Unable to read the RDS password from SSM Parameter Store"
        ) from exc

    if not password:
        raise RuntimeError(
            "SSM Parameter Store returned an empty RDS password"
        )
    return password


if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    database_url = URL.create(
        drivername="postgresql+pg8000",
        username=os.environ["DB_USER"],
        password=get_lambda_db_password(),
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
    )
else:
    database_url = settings.DATABASE_URL

engine_options = {"pool_pre_ping": True}
if isinstance(database_url, URL):
    is_sqlite = database_url.get_backend_name() == "sqlite"
else:
    is_sqlite = str(database_url).startswith("sqlite:")

if is_sqlite:
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options["pool_size"] = 1
    engine_options["max_overflow"] = 1

engine = create_engine(database_url, **engine_options)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
