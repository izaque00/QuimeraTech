"""Fase 3: Evolution Tables — genetic populations, coevolution history

Revision ID: 003
Revises: 002
Create Date: 2026-06-30
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Genetic Populations ──
    op.create_table(
        'genetic_populations',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('mission_id', sa.String(64), sa.ForeignKey('missions.id'),
                  nullable=False, index=True),
        sa.Column('generation', sa.Integer, nullable=False),
        sa.Column('population_size', sa.Integer, nullable=False),
        sa.Column('best_fitness', sa.Float, nullable=True),
        sa.Column('avg_fitness', sa.Float, nullable=True),
        sa.Column('median_fitness', sa.Float, nullable=True),
        sa.Column('diversity', sa.Float, nullable=True),
        sa.Column('pareto_front_size', sa.Integer, nullable=True),
        sa.Column('elapsed_ms', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('individuals_json', sa.JSON, nullable=True),
    )

    # ── Individuals (melhores patches por geração) ──
    op.create_table(
        'genetic_individuals',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('population_id', sa.String(64),
                  sa.ForeignKey('genetic_populations.id'), nullable=False, index=True),
        sa.Column('patch_id', sa.String(64), sa.ForeignKey('patches.id'),
                  nullable=True),
        sa.Column('patch_code', sa.Text, nullable=True),
        sa.Column('fitness_json', sa.JSON, nullable=True),
        sa.Column('generation_born', sa.Integer, nullable=False),
        sa.Column('parent_ids', sa.JSON, nullable=True),
        sa.Column('pareto_rank', sa.Integer, nullable=True),
        sa.Column('crowding_distance', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
    )

    # ── Coevolution History ──
    op.create_table(
        'coevolution_sessions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('mission_id', sa.String(64), sa.ForeignKey('missions.id'),
                  nullable=True, index=True),
        sa.Column('generation', sa.Integer, nullable=False),
        sa.Column('patch_best_fitness', sa.Float, nullable=True),
        sa.Column('test_best_effectiveness', sa.Float, nullable=True),
        sa.Column('arms_race_intensity', sa.Float, nullable=True),
        sa.Column('robust_patches_count', sa.Integer, nullable=True),
        sa.Column('elapsed_ms', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('tests_json', sa.JSON, nullable=True),
    )

    # ── Indexes ──
    op.create_index('ix_populations_mission_gen', 'genetic_populations',
                    ['mission_id', 'generation'])
    op.create_index('ix_individuals_population', 'genetic_individuals',
                    ['population_id'])
    op.create_index('ix_coevolution_mission_gen', 'coevolution_sessions',
                    ['mission_id', 'generation'])


def downgrade() -> None:
    op.drop_table('coevolution_sessions')
    op.drop_table('genetic_individuals')
    op.drop_table('genetic_populations')
