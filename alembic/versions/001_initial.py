"""Initial schema - add all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'teams',
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_id', sa.String(50), nullable=False),
        sa.Column('provider', sa.String(30), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('short_name', sa.String(10), nullable=True),
        sa.Column('league', sa.String(60), nullable=False),
        sa.Column('country', sa.String(60), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('team_id'),
    )
    op.create_index('idx_teams_external_provider', 'teams', ['external_id', 'provider'], unique=True)

    op.create_table(
        'players',
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_id', sa.String(50), nullable=False),
        sa.Column('provider', sa.String(30), nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('position', sa.String(30), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.team_id']),
        sa.PrimaryKeyConstraint('player_id'),
    )
    op.create_index('idx_players_external_provider', 'players', ['external_id', 'provider'], unique=True)

    op.create_table(
        'matches',
        sa.Column('match_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_id', sa.String(50), nullable=False),
        sa.Column('provider', sa.String(30), nullable=False),
        sa.Column('league', sa.String(60), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
        sa.Column('round', sa.String(30), nullable=True),
        sa.Column('home_team_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('away_team_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('venue', sa.String(150), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('home_score', sa.SmallInteger, nullable=True),
        sa.Column('away_score', sa.SmallInteger, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['home_team_id'], ['teams.team_id']),
        sa.ForeignKeyConstraint(['away_team_id'], ['teams.team_id']),
        sa.PrimaryKeyConstraint('match_id'),
    )
    op.create_index('idx_matches_scheduled', 'matches', ['scheduled_at'])
    op.create_index('idx_matches_league_season', 'matches', ['league', 'season'])
    op.create_index('idx_matches_external_provider', 'matches', ['external_id', 'provider'], unique=True)

    op.create_table(
        'match_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('match_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(40), nullable=False),
        sa.Column('minute', sa.SmallInteger, nullable=True),
        sa.Column('second', sa.SmallInteger, nullable=True),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('detail', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['match_id'], ['matches.match_id']),
        sa.ForeignKeyConstraint(['team_id'], ['teams.team_id']),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id']),
        sa.PrimaryKeyConstraint('event_id'),
    )
    op.create_index('idx_events_match', 'match_events', ['match_id'])

    op.create_table(
        'odds_snapshots',
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('match_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sportsbook', sa.String(60), nullable=False),
        sa.Column('market_type', sa.String(30), nullable=False),
        sa.Column('home_odds', sa.Numeric(8, 4), nullable=True),
        sa.Column('away_odds', sa.Numeric(8, 4), nullable=True),
        sa.Column('draw_odds', sa.Numeric(8, 4), nullable=True),
        sa.Column('spread_value', sa.Numeric(6, 2), nullable=True),
        sa.Column('total_value', sa.Numeric(6, 2), nullable=True),
        sa.Column('cash_pct_home', sa.Numeric(5, 2), nullable=True),
        sa.Column('ticket_pct_home', sa.Numeric(5, 2), nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['matches.match_id']),
        sa.PrimaryKeyConstraint('snapshot_id'),
    )
    op.create_index('idx_odds_unique', 'odds_snapshots', ['match_id', 'sportsbook', 'market_type', 'captured_at'], unique=True)
    op.create_index('idx_odds_match_time', 'odds_snapshots', ['match_id', 'captured_at'])

    op.create_table(
        'player_biometrics',
        sa.Column('biometric_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(30), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metric_type', sa.String(50), nullable=False),
        sa.Column('value', sa.Numeric(12, 4), nullable=False),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id']),
        sa.PrimaryKeyConstraint('biometric_id'),
    )
    op.create_index('idx_bio_unique', 'player_biometrics', ['player_id', 'source', 'metric_type', 'recorded_at'], unique=True)
    op.create_index('idx_bio_player_time', 'player_biometrics', ['player_id', 'recorded_at'])

    op.create_table(
        'sentiment_scores',
        sa.Column('sentiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(10), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(30), nullable=False),
        sa.Column('score', sa.Numeric(5, 4), nullable=False),
        sa.Column('volume', sa.Integer, nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('sentiment_id'),
    )
    op.create_index('idx_sent_entity_time', 'sentiment_scores', ['entity_type', 'entity_id', 'captured_at'])

    op.create_table(
        'feature_store',
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('match_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('features', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['matches.match_id']),
        sa.PrimaryKeyConstraint('feature_id'),
    )
    op.create_index('idx_features_match', 'feature_store', ['match_id'])

    op.create_table(
        'predictions',
        sa.Column('prediction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('match_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_name', sa.String(60), nullable=False),
        sa.Column('model_version', sa.String(20), nullable=False),
        sa.Column('predicted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('home_win_prob', sa.Numeric(5, 4), nullable=True),
        sa.Column('draw_prob', sa.Numeric(5, 4), nullable=True),
        sa.Column('away_win_prob', sa.Numeric(5, 4), nullable=True),
        sa.Column('predicted_home_score', sa.Numeric(4, 2), nullable=True),
        sa.Column('predicted_away_score', sa.Numeric(4, 2), nullable=True),
        sa.Column('shap_values', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_live', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['match_id'], ['matches.match_id']),
        sa.PrimaryKeyConstraint('prediction_id'),
    )
    op.create_index('idx_pred_match', 'predictions', ['match_id'])


def downgrade() -> None:
    op.drop_table('predictions')
    op.drop_table('feature_store')
    op.drop_table('sentiment_scores')
    op.drop_table('player_biometrics')
    op.drop_table('odds_snapshots')
    op.drop_table('match_events')
    op.drop_table('matches')
    op.drop_table('players')
    op.drop_table('teams')
