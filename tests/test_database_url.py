from saarthi.storage.sqlite import normalize_database_url


def test_normalizes_railway_postgresql_url_for_asyncpg() -> None:
    assert (
        normalize_database_url("postgresql://user:secret@host:5432/railway")
        == "postgresql+asyncpg://user:secret@host:5432/railway"
    )


def test_normalizes_legacy_postgres_url_for_asyncpg() -> None:
    assert (
        normalize_database_url("postgres://user:secret@host/db")
        == "postgresql+asyncpg://user:secret@host/db"
    )


def test_preserves_sqlite_url() -> None:
    database_url = "sqlite+aiosqlite:///./saarthi.db"
    assert normalize_database_url(database_url) == database_url
