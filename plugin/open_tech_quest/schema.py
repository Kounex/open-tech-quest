"""Compatibility for CTFd's SQLite plugin runner, which only calls create_all."""
from importlib import import_module
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from CTFd.models import db


def upgrade_sqlite_attendance():
    if db.engine.dialect.name != "sqlite":
        return
    migration = import_module("CTFd.plugins.open_tech_quest.migrations.0005_attendance")
    with db.engine.connect() as connection:
        with connection.begin():
            # Serialize introspection and ALTERs across starting workers.
            connection.execute(text("BEGIN IMMEDIATE"))
            migration.upgrade(Operations(MigrationContext.configure(connection)))
