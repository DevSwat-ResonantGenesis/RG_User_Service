"""Initial schema — user_profiles, user_preferences, org_settings, activity_log

Revision ID: 001
Revises: None
Create Date: 2026-04-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    op.create_table(
        "user_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("chat", JSONB, nullable=False, server_default="{}"),
        sa.Column("agent", JSONB, nullable=False, server_default="{}"),
        sa.Column("display", JSONB, nullable=False, server_default="{}"),
        sa.Column("notifications", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    op.create_table(
        "org_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("slug", sa.String(128), nullable=True, index=True),
        sa.Column("branding", JSONB, nullable=False, server_default="{}"),
        sa.Column("feature_flags", JSONB, nullable=False, server_default="{}"),
        sa.Column("default_preferences", JSONB, nullable=False, server_default="{}"),
        sa.Column("settings", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", name="uq_org_settings_org_id"),
    )

    op.create_table(
        "activity_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("org_id", sa.String(64), nullable=True, index=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default="{}"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_activity_user_ts", "activity_log", ["user_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_activity_user_ts", table_name="activity_log")
    op.drop_table("activity_log")
    op.drop_table("org_settings")
    op.drop_table("user_preferences")
    op.drop_table("user_profiles")
