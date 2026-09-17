from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session
from pathlib import Path
from functools import lru_cache
import os

def get_database_url() -> str:
    """
    Get the database URL.

    Resolution order:
      1. MISS_PAULING_DB_URL   - full SQLAlchemy URL (e.g. postgresql://... or sqlite:////data/sqlite.db)
      2. MISS_PAULING_DB_PATH  - path to a SQLite file (e.g. a mounted volume in Kubernetes)
      3. <repo>/db/sqlite.db   - local development default
    """
    url = os.environ.get("MISS_PAULING_DB_URL")
    if url:
        return url

    db_path = Path(os.environ.get("MISS_PAULING_DB_PATH") or Path(__file__).parent.parent / "db" / "sqlite.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"

@lru_cache()
def get_engine():
    """Create a singleton database engine"""
    url = get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)

# Base class for database models using SQLAlchemy 2.0+
class Base(DeclarativeBase):
    pass

# Export singleton instances
engine = get_engine()

# Dependency to get a database session
def get_db():
    """Get a database session using SQLAlchemy 2.0+ Session"""
    with Session(engine) as session:
        yield session
