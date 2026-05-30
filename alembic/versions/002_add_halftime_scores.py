"""Add home_halftime_score and away_halftime_score to matches

Revision ID: 002_add_halftime_scores
Revises: 001_initial
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_add_halftime_scores'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('matches', sa.Column('home_halftime_score', sa.SmallInteger, nullable=True))
    op.add_column('matches', sa.Column('away_halftime_score', sa.SmallInteger, nullable=True))


def downgrade() -> None:
    op.drop_column('matches', 'away_halftime_score')
    op.drop_column('matches', 'home_halftime_score')
