# Database Migrations

LexiBridge AI uses Flask-Migrate, which wires Alembic into the existing
Flask-SQLAlchemy app. Migration scripts are versioned under `migrations/`.

The current migration baseline creates the v0.1 local MVP schema:

- `term`
- `feedback`
- `knowledge_document`
- `knowledge_chunk`

It also includes the layout metadata columns used by the document layout
pipeline.

## Local Commands

Run commands from the repository root:

```bash
PYTHONPATH=backend FLASK_APP=app .venv/bin/flask db upgrade
```

Generate a new migration after changing SQLAlchemy models:

```bash
PYTHONPATH=backend FLASK_APP=app .venv/bin/flask db migrate -m "describe schema change"
```

Review the generated file under `migrations/versions/` before committing it.
Alembic autogenerate is a starting point, not a substitute for review.

## Existing Local SQLite Databases

The initial migration is intended for new databases. Older local SQLite files
that were created before migrations may already contain the core tables but may
not contain `alembic_version`.

For now, the app still keeps the lightweight SQLite compatibility helper for
layout columns during direct local startup. Before using migrations with an
existing local database, inspect the schema and either:

1. back up the database and migrate a fresh copy, or
2. stamp the existing database after confirming that its schema matches the
   initial migration.

Do not run destructive migration commands on a local database that contains
useful uploaded-course evidence without a backup.
