from alembic import context
from app.models import Base
from app.database import engine


# Run portable migrations inside a database transaction.
def run_migrations_online():
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
