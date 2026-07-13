"""merge migration heads

Revision ID: 37658c025e71
Revises: 202607120001, 202607120002
Create Date: 2026-07-12 14:29:13.895475
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37658c025e71'
down_revision: Union[str, Sequence[str], None] = ('202607120001', '202607120002')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
