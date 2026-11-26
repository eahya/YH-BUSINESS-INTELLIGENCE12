from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_options = {"pool_pre_ping": True, "connect_args": connect_args}
if settings.database_url.startswith("mssql+pyodbc"):
    engine_options["fast_executemany"] = True
engine = create_engine(settings.database_url, **engine_options)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        if engine.dialect.name == "mssql":
            db.execute(text("EXEC sys.sp_set_session_context @key=N'company_id', @value=NULL"))
            db.commit()
        yield db
    finally:
        db.close()
