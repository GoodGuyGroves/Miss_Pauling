from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, text
from sqlalchemy import pool

from alembic import context

# Add the parent directory to sys.path to allow imports from the app package
parent_dir = str(Path(__file__).parent.parent.parent.parent)
sys.path.append(parent_dir)

# Import our models and database configuration
from app.db.database import get_database_url, Base
from app.db.models import User, UserSession  # Import all models here for Alembic to detect

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the SQLAlchemy URL with the one from our app configuration
config.set_main_option("sqlalchemy.url", get_database_url())

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # For SQLite, we need to support foreign keys
    config_section = config.get_section(config.config_ini_section)
    if 'sqlite' in config.get_main_option("sqlalchemy.url"):
        config_section['sqlalchemy.url'] = config.get_main_option("sqlalchemy.url")
        
        # Add SQLite-specific configuration for foreign keys
        connectable = engine_from_config(
            config_section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            connect_args={"check_same_thread": False}
        )
    else:
        connectable = engine_from_config(
            config_section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        # For SQLite, enable foreign keys - using text() for proper SQLAlchemy execution
        if connection.dialect.name == 'sqlite':
            connection.execute(text('PRAGMA foreign_keys=ON'))
            
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            # For SQLite, these options are recommended
            render_as_batch=connection.dialect.name == 'sqlite'
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
