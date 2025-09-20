# alembic/versions/add_sent_at_to_outbox.py
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# עדכן את ה-revision וה-down_revision שלכם בהתאם
revision = "add_sent_at_to_outbox"
down_revision = "d19886db2f05"  # זה ה-HEAD האחרון שציינת קודם
branch_labels = None
depends_on = None

def _has_column(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols

def upgrade():
    conn = op.get_bind()
    # הוסף sent_at אם חסר
    if not _has_column(conn, "outbox", "sent_at"):
        with op.batch_alter_table("outbox") as b:
            b.add_column(sa.Column("sent_at", sa.DateTime(), nullable=True))

def downgrade():
    # לא נדרש כרגע (השאר ריק)
    pass
