"""add item_id to outbox (idempotent)
Revision ID: d19886db2f05
Revises: 5ddb5bb9f504
Create Date: 2025-09-19
"""
from alembic import op
import sqlalchemy as sa

revision = "d19886db2f05"
down_revision = "5ddb5bb9f504"  # השאר את זה כמו אצלך בהיסטוריה
branch_labels = None
depends_on = None

def _has_column_sqlite(bind, table, col):
    # SQLite: PRAGMA table_info
    rows = bind.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    # rows: (cid, name, type, notnull, dflt_value, pk)
    return any(r[1] == col for r in rows)

def upgrade():
    bind = op.get_bind()
    with op.batch_alter_table("outbox") as b:
        if not _has_column_sqlite(bind, "outbox", "item_id"):
            b.add_column(sa.Column("item_id", sa.Integer(), nullable=True))

def downgrade():
    bind = op.get_bind()
    with op.batch_alter_table("outbox") as b:
        if _has_column_sqlite(bind, "outbox", "item_id"):
            b.drop_column("item_id")
