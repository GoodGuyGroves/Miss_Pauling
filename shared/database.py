from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session
from pathlib import Path
from functools import lru_cache

def get_database_url():
    """Get database URL for shared SQLite database"""
    # Use the shared database in the db/ folder
    db_path = Path(__file__).parent.parent / "db" / "sqlite.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"

@lru_cache()
def get_engine():
    """Create a singleton database engine"""
    return create_engine(
        get_database_url(),
        connect_args={"check_same_thread": False}  # Needed for SQLite
    )

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