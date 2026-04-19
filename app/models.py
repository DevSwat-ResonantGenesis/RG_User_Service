"""Data models for User Service — profiles, preferences, org settings, activity."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Index, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from .db import Base


class UserProfile(Base):
    """Extended user profile (identity lives in RG_Auth, this is the 'how you look' layer)."""
    __tablename__ = "user_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(1024), nullable=True)
    bio = Column(Text, nullable=True)
    timezone = Column(String(64), default="UTC", nullable=False)
    language = Column(String(16), default="en", nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UserPreferences(Base):
    """Per-user preferences (chat, agent, display, notifications)."""
    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False, index=True)
    chat = Column(JSONB, default=dict, nullable=False)
    agent = Column(JSONB, default=dict, nullable=False)
    display = Column(JSONB, default=dict, nullable=False)
    notifications = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class OrgSettings(Base):
    """Per-organization settings scoped by org_id."""
    __tablename__ = "org_settings"
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_org_settings_org_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    slug = Column(String(128), nullable=True, index=True)
    branding = Column(JSONB, default=dict, nullable=False)
    feature_flags = Column(JSONB, default=dict, nullable=False)
    default_preferences = Column(JSONB, default=dict, nullable=False)
    settings = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ActivityLog(Base):
    """Aggregated activity log — pulled from Auth, Billing, Chat, AgentEngine."""
    __tablename__ = "activity_log"
    __table_args__ = (
        Index("ix_activity_user_ts", "user_id", "timestamp"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False, index=True)
    org_id = Column(String(64), nullable=True, index=True)
    source = Column(String(32), nullable=False)  # auth, billing, chat, agent_engine
    action = Column(String(128), nullable=False)  # login, credit_used, message_sent, agent_run
    detail = Column(JSONB, default=dict, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
