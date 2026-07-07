"""Fase 1: Core Tables — missions, patches, agents

Create initial schema for Quimera Mark X core operations.

Revision ID: 001
Revises: None
Create Date: 2026-06-30
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Missions ──
    op.create_table(
        'missions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('type', sa.String(32), nullable=False, index=True),
        sa.Column('status', sa.String(16), nullable=False, default='pending',
                  server_default='pending'),
        sa.Column('target_file', sa.String(512), nullable=False),
        sa.Column('original_code', sa.Text, nullable=True),
        sa.Column('patched_code', sa.Text, nullable=True),
        sa.Column('error_context', sa.Text, nullable=True),
        sa.Column('language', sa.String(16), nullable=False, default='c',
                  server_default='c'),
        sa.Column('priority', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('max_attempts', sa.Integer, nullable=False, default=3,
                  server_default='3'),
        sa.Column('attempt_count', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('metadata_json', sa.JSON, nullable=True),
    )

    # ── Patches ──
    op.create_table(
        'patches',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('mission_id', sa.String(64), sa.ForeignKey('missions.id'),
                  nullable=False, index=True),
        sa.Column('patch_code', sa.Text, nullable=False),
        sa.Column('original_code', sa.Text, nullable=True),
        sa.Column('diff_unified', sa.Text, nullable=True),
        sa.Column('fitness_score', sa.Float, nullable=True),
        sa.Column('generation', sa.Integer, nullable=True),
        sa.Column('status', sa.String(16), nullable=False, default='pending',
                  server_default='pending'),
        sa.Column('created_by_agent', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('applied_at', sa.DateTime, nullable=True),
        sa.Column('metadata_json', sa.JSON, nullable=True),
    )

    # ── Agents ──
    op.create_table(
        'agents',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('type', sa.String(32), nullable=False, index=True),
        sa.Column('language', sa.String(16), nullable=False),
        sa.Column('version', sa.String(16), nullable=False, default='1.0.0',
                  server_default='1.0.0'),
        sa.Column('status', sa.String(16), nullable=False, default='active',
                  server_default='active'),
        sa.Column('total_missions', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('successful_missions', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('avg_fitness', sa.Float, nullable=True),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('config_json', sa.JSON, nullable=True),
    )

    # ── Indexes ──
    op.create_index('ix_missions_status_created', 'missions',
                    ['status', 'created_at'])
    op.create_index('ix_patches_mission_status', 'patches',
                    ['mission_id', 'status'])
    op.create_index('ix_agents_language_status', 'agents',
                    ['language', 'status'])


def downgrade() -> None:
    op.drop_table('patches')
    op.drop_table('missions')
    op.drop_table('agents')
