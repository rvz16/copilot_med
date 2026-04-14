from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base


class Database:
    """Small database wrapper that owns the SQLAlchemy engine and sessions."""

    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, connect_args=connect_args)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def create_tables(self) -> None:
        Base.metadata.create_all(bind=self.engine)
        self._apply_compatible_migrations()

    def session(self) -> Session:
        return self.session_factory()

    def get_session(self) -> Generator[Session, None, None]:
        db = self.session()
        try:
            yield db
        finally:
            db.close()

    def dispose(self) -> None:
        self.engine.dispose()

    def _apply_compatible_migrations(self) -> None:
        inspector = inspect(self.engine)
        if "session_profiles" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("session_profiles")}
        if "llm_config_json" in columns:
            return

        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE session_profiles ADD COLUMN llm_config_json JSON"))
