
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(url: str) -> str:
    # Compatibilidade com formatos comuns de URLs PostgreSQL.
    if url.startswith("postgres://"):
        return url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )

    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return url


database_url = normalize_database_url(settings.database_url)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
    pool_timeout=10,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
