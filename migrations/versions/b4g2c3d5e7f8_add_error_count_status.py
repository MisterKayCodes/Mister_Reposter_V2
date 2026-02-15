"""add error_count and status columns

Revision ID: b4g2c3d5e7f8
Revises: a3f1b2c4d5e6
Create Date: 2026-02-14 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b4g2c3d5e7f8'
down_revision: Union[str, None] = 'a3f1b2c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('repost_pairs', sa.Column('error_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('repost_pairs', sa.Column('status', sa.String(16), server_default='active', nullable=False))


def downgrade() -> None:
    op.drop_column('repost_pairs', 'status')
    op.drop_column('repost_pairs', 'error_count')
