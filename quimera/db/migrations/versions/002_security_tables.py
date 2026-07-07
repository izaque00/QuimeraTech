"""Fase 2: Security Tables — vulnerabilities, exploits, CVE cache

Revision ID: 002
Revises: 001
Create Date: 2026-06-30
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Vulnerabilities ──
    op.create_table(
        'vulnerabilities',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('patch_id', sa.String(64), sa.ForeignKey('patches.id'),
                  nullable=True, index=True),
        sa.Column('cve_id', sa.String(32), nullable=True, index=True),
        sa.Column('type', sa.String(32), nullable=False, index=True),
        sa.Column('severity', sa.String(16), nullable=False, default='MEDIUM',
                  server_default='MEDIUM'),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('location_file', sa.String(256), nullable=True),
        sa.Column('location_line', sa.Integer, nullable=True),
        sa.Column('exploit_code', sa.Text, nullable=True),
        sa.Column('remediation', sa.Text, nullable=True),
        sa.Column('status', sa.String(16), nullable=False, default='open',
                  server_default='open'),
        sa.Column('detected_by', sa.String(64), nullable=True),
        sa.Column('detected_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('metadata_json', sa.JSON, nullable=True),
    )

    # ── CVE Cache ──
    op.create_table(
        'cve_cache',
        sa.Column('cve_id', sa.String(32), primary_key=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('severity', sa.String(16), nullable=True),
        sa.Column('cvss_score', sa.Float, nullable=True),
        sa.Column('cwe_ids', sa.JSON, nullable=True),
        sa.Column('affected_products', sa.JSON, nullable=True),
        sa.Column('patch_links', sa.JSON, nullable=True),
        sa.Column('published_date', sa.DateTime, nullable=True),
        sa.Column('last_modified', sa.DateTime, nullable=True),
        sa.Column('fetched_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('raw_json', sa.JSON, nullable=True),
    )

    # ── Fuzzing Sessions ──
    op.create_table(
        'fuzzing_sessions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('target_file', sa.String(256), nullable=False),
        sa.Column('strategy', sa.String(32), nullable=False, default='mutation',
                  server_default='mutation'),
        sa.Column('total_iterations', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('unique_crashes', sa.Integer, nullable=False, default=0,
                  server_default='0'),
        sa.Column('coverage_pct', sa.Float, nullable=True),
        sa.Column('executions_per_second', sa.Float, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('duration_ms', sa.Float, nullable=True),
        sa.Column('crash_data', sa.JSON, nullable=True),
    )

    # ── Indexes ──
    op.create_index('ix_vulns_severity_status', 'vulnerabilities',
                    ['severity', 'status'])
    op.create_index('ix_vulns_cve', 'vulnerabilities', ['cve_id'])
    op.create_index('ix_cve_cache_fetched', 'cve_cache', ['fetched_at'])


def downgrade() -> None:
    op.drop_table('fuzzing_sessions')
    op.drop_table('cve_cache')
    op.drop_table('vulnerabilities')
