from alembic import context
from app.models_review_content import ReviewContentBase as Base


def run_migrations_online():
    from app.database import engine

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline():
    from app.config import settings

    # Compile a review artifact only. No engine, credential or connection is created.
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
