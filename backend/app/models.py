from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    idea: Mapped[str] = mapped_column(Text, default="", nullable=False)
    domain: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    projections: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    proposals: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    audit: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    nodes: Mapped[list["Node"]] = relationship("Node", back_populates="workspace", cascade="all, delete-orphan")
    links: Mapped[list["Link"]] = relationship("Link", back_populates="workspace", cascade="all, delete-orphan")
    slots: Mapped[list["Slot"]] = relationship("Slot", back_populates="workspace", cascade="all, delete-orphan")
    choice_groups: Mapped[list["ChoiceGroup"]] = relationship(
        "ChoiceGroup", back_populates="workspace", cascade="all, delete-orphan"
    )
    issues: Mapped[list["Issue"]] = relationship("Issue", back_populates="workspace", cascade="all, delete-orphan")


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    scope_status: Mapped[str | None] = mapped_column(String(64), index=True)
    source: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    slots: Mapped[list[str] | None] = mapped_column(JSON)
    extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="nodes")


class Link(Base):
    __tablename__ = "links"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    source: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="links")


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    owner_node_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    expected_kinds: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    arity: Mapped[str] = mapped_column(String(16), default="many", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="empty", nullable=False)
    choice_group_id: Mapped[str | None] = mapped_column(String(128), index=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="slots")


class ChoiceGroup(Base):
    __tablename__ = "choice_groups"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    slot_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    selected_choice_id: Mapped[str | None] = mapped_column(String(128), index=True)
    selection_mode: Mapped[str] = mapped_column(String(16), default="single", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="choice_groups")
    choices: Mapped[list["Choice"]] = relationship("Choice", back_populates="choice_group", cascade="all, delete-orphan")


class Choice(Base):
    __tablename__ = "choices"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    choice_group_id: Mapped[str] = mapped_column(ForeignKey("choice_groups.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proposed_node_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    proposed_link_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    impact_preview: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False)

    choice_group: Mapped["ChoiceGroup"] = relationship("ChoiceGroup", back_populates="choices")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="missing", nullable=False)
    related_node_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    suggested_projection: Mapped[str] = mapped_column(String(32), default="goal", nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    source: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="issues")
