from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


# One source of truth on Windows, containers and Lambda alike. Configure RDS
# credentials/TLS through DATABASE_URL; importing the app never calls AWS SSM.
database_url = settings.DATABASE_URL
if not database_url:
    raise RuntimeError("DATABASE_URL must be configured")

engine_options = {"pool_pre_ping": True, "hide_parameters": True}
if database_url.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options["pool_size"] = 1
    engine_options["max_overflow"] = 1

engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
