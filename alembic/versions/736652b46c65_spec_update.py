from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '736652b46c65'
down_revision = '8a1f12376bcd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("outbox") as b:
        b.add_column(sa.Column("item_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("sent_at", sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table("outbox") as b:
        b.drop_column("item_id")
        b.drop_column("created_at")
        b.drop_column("sent_at")
