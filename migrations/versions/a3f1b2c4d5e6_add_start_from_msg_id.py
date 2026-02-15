"""add start_from_msg_id

Revision ID: a3f1b2c4d5e6
Revises: 97e0d9f12ec9
Create Date: 2026-02-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3f1b2c4d5e6'
down_revision: Union[str, None] = '97e0d9f12ec9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('repost_pairs', sa.Column('start_from_msg_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('repost_pairs', 'start_from_msg_id')
