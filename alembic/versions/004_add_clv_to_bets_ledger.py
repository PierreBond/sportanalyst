"""Add closing_odds and clv_pct to bets_ledger for CLV tracking.

Revision ID: 004_add_clv_to_bets_ledger
Revises: 003_create_bets_ledger
Create Date: 2026-11-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '004_add_clv_to_bets_ledger'
down_revision: Union[str, None] = '003_create_bets_ledger'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bets_ledger', sa.Column('closing_odds', sa.Numeric(7, 2), nullable=True))
    op.add_column('bets_ledger', sa.Column('clv_pct', sa.Numeric(6, 4), nullable=True))


def downgrade() -> None:
    op.drop_column('bets_ledger', 'clv_pct')
    op.drop_column('bets_ledger', 'closing_odds')
