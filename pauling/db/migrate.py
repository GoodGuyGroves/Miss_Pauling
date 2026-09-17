"""Bring the database to the latest Alembic revision at application startup.

Safe here because the app runs as a single replica; two processes migrating the
same database concurrently could race. If that ever changes, move this into a
Kubernetes Job or init container and delete the call from pauling/main.py.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "pauling" / "migrations"

# Revision that matches the schema `Base.metadata.create_all` produced before
# Alembic was introduced. Databases from that era have the tables but no
# alembic_version table; they are stamped here instead of re-created.
BASELINE_REVISION = "253fab92af9a"


def _alembic_config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))  # absolute: independent of cwd
    cfg.attributes["configure_logging"] = False  # don't let env.py reconfigure uvicorn's logging
    return cfg


def run_migrations(engine: Engine) -> None:
    """Upgrade `engine`'s database to head, stamping pre-Alembic databases first."""
    tables = set(inspect(engine).get_table_names())
    cfg = _alembic_config()
    if "alembic_version" not in tables and "users" in tables:
        print(f"Database predates Alembic; stamping baseline revision {BASELINE_REVISION}")
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")
