"""Alembic environment: SQLite, batch mode, schema taken from the table specs."""

from sqlalchemy import create_engine

from alembic import context
from footystreams.persistence.sql.tables import METADATA

config = context.config
target_metadata = METADATA


def _run(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Use the connection handed in by the caller, else build an engine from -x url=... ."""
    supplied = config.attributes.get("connection")
    if supplied is not None:
        _run(supplied)
        return
    url = context.get_x_argument(as_dictionary=True).get("url") or config.get_main_option(
        "sqlalchemy.url"
    )
    engine = create_engine(url)
    with engine.connect() as connection:
        _run(connection)


run_migrations_online()
