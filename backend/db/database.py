from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path
import json

# Load database config from config file or environment variables
def get_database_url():
    """Get database URL from config or environment variables"""
    config_path = Path(__file__).parent.parent / "config.json"
    
    # Default database configuration for SQLite
    db_config = {
        "path": os.environ.get("DB_PATH", str(Path(__file__).parent.parent.parent / "sqlite.db")),
    }
    
    # Load from config file if it exists
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
                
            if "database" in config_data and "path" in config_data["database"]:
                db_config.update({"path": config_data["database"]["path"]})
        except Exception as e:
            print(f"Error loading database config: {e}")
    
    # Make the directory if it doesn't exist
    db_dir = Path(db_config["path"]).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # Construct the database URL for SQLite
    return f"sqlite:///{db_config['path']}"

# Create database engine
engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Session factory for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for database models
Base = declarative_base()

# Dependency to get a database session
def get_db():
    """Get a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()