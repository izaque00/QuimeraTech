"""Fase 4: Multi-Language Tables — plugin registry, language-specific data

Revision ID: 004
Revises: 003
Create Date: 2026-06-30
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Plugin Registry ──
    op.create_table(
        'plugin_registry',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('language', sa.String(32), nullable=False, index=True),
        sa.Column('version', sa.String(16), nullable=False, default='1.0.0',
                  server_default='1.0.0'),
        sa.Column('class_name', sa.String(128), nullable=False),
        sa.Column('module_path', sa.String(256), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, default='active',
                  server_default='active'),
        sa.Column('capabilities', sa.JSON, nullable=True),
        sa.Column('registered_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('last_health_check', sa.DateTime, nullable=True),
        sa.Column('metadata_json', sa.JSON, nullable=True),
    )

    # ── Multi-Language Files ──
    op.create_table(
        'multi_lang_files',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('language', sa.String(32), nullable=False, index=True),
        sa.Column('original_code', sa.Text, nullable=True),
        sa.Column('patched_code', sa.Text, nullable=True),
        sa.Column('issues_found', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('issues_fixed', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('agent_used', sa.String(64), nullable=True),
        sa.Column('verified', sa.Boolean, nullable=False, default=False,
                  server_default='false'),
        sa.Column('processed_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('repair_duration_ms', sa.Float, nullable=True),
        sa.Column('issues_json', sa.JSON, nullable=True),
    )

    # ── IDE Plugin Sessions ──
    op.create_table(
        'ide_sessions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('ide_type', sa.String(32), nullable=False),  # vscode, jetbrains, neovim
        sa.Column('ide_version', sa.String(32), nullable=True),
        sa.Column('workspace_path', sa.String(512), nullable=True),
        sa.Column('files_processed', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('total_repairs', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('session_start', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('session_end', sa.DateTime, nullable=True),
        sa.Column('commands_executed', sa.JSON, nullable=True),
    )

    # ── Supply Chain Checks ──
    op.create_table(
        'supply_chain_checks',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('file_path', sa.String(512), nullable=False, index=True),
        sa.Column('patch_id', sa.String(64), sa.ForeignKey('patches.id'),
                  nullable=True),
        sa.Column('vulnerable_deps', sa.JSON, nullable=True),
        sa.Column('license_issues', sa.JSON, nullable=True),
        sa.Column('third_party_detected', sa.Boolean, nullable=False,
                  default=False, server_default='false'),
        sa.Column('risk_score', sa.Float, nullable=True),
        sa.Column('checked_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
    )

    # ── Indexes ──
    op.create_index('ix_plugin_registry_lang_status', 'plugin_registry',
                    ['language', 'status'])
    op.create_index('ix_multi_lang_files_lang', 'multi_lang_files',
                    ['language', 'processed_at'])
    op.create_index('ix_supply_chain_file', 'supply_chain_checks',
                    ['file_path'])


def downgrade() -> None:
    op.drop_table('supply_chain_checks')
    op.drop_table('ide_sessions')
    op.drop_table('multi_lang_files')
    op.drop_table('plugin_registry')
