"""Drop unused verification_codes table

Revision ID: 20260219_drop_verification_codes
Revises: 20260219_entity_name_alignment
Create Date: 2026-02-19 17:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260219_drop_verification_codes"
down_revision = "20260219_entity_name_alignment"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name):
    return table_name in _inspector().get_table_names()


def upgrade():
    if _has_table("verification_codes"):
        op.drop_table("verification_codes")


def downgrade():
    if not _has_table("verification_codes"):
        op.create_table(
            "verification_codes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("Instructor.InstructorID"), nullable=False),
            sa.Column("code", sa.String(length=128), nullable=False),
            sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("purpose", sa.String(length=64), nullable=True),
        )
