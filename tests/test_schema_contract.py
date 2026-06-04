from pathlib import Path

from operator_day.models import Base


def test_every_business_table_except_tenants_has_tenant_id() -> None:
    skipped = {"tenants"}

    for table_name, table in Base.metadata.tables.items():
        if table_name in skipped:
            continue
        assert "tenant_id" in table.columns, table_name


def test_initial_migration_mentions_every_model_table() -> None:
    migration = Path("alembic/versions/0001_core_schema.py").read_text(encoding="utf-8")

    for table_name in Base.metadata.tables:
        assert f'"{table_name}"' in migration, table_name
