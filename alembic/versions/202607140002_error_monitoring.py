"""add continuous error monitoring aggregates

Revision ID: 202607140002
Revises: 202607140001
Create Date: 2026-07-14 14:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "202607140002"
down_revision: Union[str, Sequence[str], None] = "202607140001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_groups",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("environment", sa.String(length=128), nullable=False),
        sa.Column("component", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=71), nullable=False),
        sa.Column("error_type", sa.String(length=256), nullable=False),
        sa.Column("normalized_message", sa.Text(), nullable=False),
        sa.Column("highest_severity", sa.String(length=16), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurrence_count", sa.BigInteger(), nullable=False),
        sa.Column("latest_source", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "latest_repository",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("latest_release", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "latest_correlation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("sample", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sample_hash", sa.String(length=71), nullable=False),
        sa.Column("redaction_status", sa.String(length=16), nullable=False),
        sa.Column("redaction_policy_version", sa.String(length=128), nullable=False),
        sa.Column("redaction_count", sa.Integer(), nullable=False),
        sa.Column("active_issue_id", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "highest_severity IN ('warning', 'error', 'critical')",
            name="ck_error_groups_severity",
        ),
        sa.CheckConstraint(
            "occurrence_count > 0",
            name="ck_error_groups_occurrence_count",
        ),
        sa.CheckConstraint(
            "redaction_status = 'sanitized'",
            name="ck_error_groups_redaction_status",
        ),
        sa.ForeignKeyConstraint(["active_issue_id"], ["issues.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("active_issue_id", name="uq_error_groups_active_issue"),
        sa.UniqueConstraint(
            "project_id",
            "environment",
            "component",
            "fingerprint",
            name="uq_error_groups_identity",
        ),
    )
    op.create_index(
        "ix_error_groups_project_last_seen",
        "error_groups",
        ["project_id", "last_seen_at"],
        unique=False,
    )
    op.create_index(
        "ix_error_groups_project_severity",
        "error_groups",
        ["project_id", "highest_severity"],
        unique=False,
    )
    op.create_table(
        "error_event_receipts",
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("group_id", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=71), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["error_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "event_id"),
    )
    op.create_index(
        "ix_error_event_receipts_group_id",
        "error_event_receipts",
        ["group_id"],
        unique=False,
    )
    op.create_table(
        "error_occurrence_buckets",
        sa.Column("group_id", sa.String(length=128), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurrence_count", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "occurrence_count > 0",
            name="ck_error_buckets_occurrence_count",
        ),
        sa.ForeignKeyConstraint(["group_id"], ["error_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "bucket_start"),
    )


def downgrade() -> None:
    op.drop_table("error_occurrence_buckets")
    op.drop_index("ix_error_event_receipts_group_id", table_name="error_event_receipts")
    op.drop_table("error_event_receipts")
    op.drop_index("ix_error_groups_project_severity", table_name="error_groups")
    op.drop_index("ix_error_groups_project_last_seen", table_name="error_groups")
    op.drop_table("error_groups")
