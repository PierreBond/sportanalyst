"""Create bets_ledger for live value-bet tracking

Revision ID: 003_create_bets_ledger
Revises: 002_add_halftime_scores
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003_create_bets_ledger'
down_revision: Union[str, None] = '002_add_halftime_scores'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bets_ledger',
        sa.Column('bet_id', sa.Uuid, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('match_id', sa.Uuid, sa.ForeignKey('matches.match_id'), nullable=False),
        sa.Column('selection', sa.String(10), nullable=False),
        sa.Column('model_prob', sa.Numeric(5, 4), nullable=False),
        sa.Column('odds', sa.Numeric(7, 2), nullable=False),
        sa.Column('edge', sa.Numeric(6, 4), nullable=False),
        sa.Column('stake_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('sportsbook', sa.String(40), nullable=False),
        sa.Column('flagged_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('won', sa.Boolean, nullable=True),
        sa.Column('pnl_pct', sa.Numeric(7, 4), nullable=True),
        sa.UniqueConstraint('match_id', 'selection', 'sportsbook'),
    )


def downgrade() -> None:
    op.drop_table('bets_ledger')
