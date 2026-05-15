from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    idea: Mapped[str] = mapped_column(Text, default="", nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    projections: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
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
    proposals: Mapped[list["Proposal"]] = relationship("Proposal", back_populates="workspace", cascade="all, delete-orphan")


class Node(Base):
    __tablename__ = "nodes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_nodes_workspace_id_id"),
        Index("ix_nodes_workspace_kind", "workspace_id", "kind"),
        Index("ix_nodes_workspace_status", "workspace_id", "status"),
        Index("ix_nodes_workspace_scope_status", "workspace_id", "scope_status"),
        {"sqlite_autoincrement": True},
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    id: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    scope_status: Mapped[str | None] = mapped_column(String(64), index=True)
    source: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="nodes")


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_links_workspace_id_id"),
        Index("ix_links_workspace_type", "workspace_id", "type"),
        Index("ix_links_workspace_source", "workspace_id", "source_id"),
        Index("ix_links_workspace_target", "workspace_id", "target_id"),
        ForeignKeyConstraint(
            ["workspace_id", "source_id"],
            ["nodes.workspace_id", "nodes.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "target_id"],
            ["nodes.workspace_id", "nodes.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
        {"sqlite_autoincrement": True},
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    source: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="links")


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_slots_workspace_id_id"),
        Index("ix_slots_workspace_owner", "workspace_id", "owner_node_id"),
        Index("ix_slots_workspace_projection", "workspace_id", "owner_projection"),
        ForeignKeyConstraint(
            ["workspace_id", "owner_node_id"],
            ["nodes.workspace_id", "nodes.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
        {"sqlite_autoincrement": True},
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_node_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    owner_projection: Mapped[str | None] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    expected_kinds: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    arity: Mapped[str] = mapped_column(String(16), default="many", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="empty", nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="slots")


class ChoiceGroup(Base):
    __tablename__ = "choice_groups"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_choice_groups_workspace_id_id"),
        Index("ix_choice_groups_workspace_slot", "workspace_id", "slot_id"),
        Index("ix_choice_groups_workspace_status", "workspace_id", "status"),
        ForeignKeyConstraint(
            ["workspace_id", "slot_id"],
            ["slots.workspace_id", "slots.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
        {"sqlite_autoincrement": True},
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    id: Mapped[str] = mapped_column(String(128), nullable=False)
    slot_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    selected_choice_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    selection_mode: Mapped[str] = mapped_column(String(16), default="single", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="choice_groups")
    choices: Mapped[list["Choice"]] = relationship(
        "Choice",
        back_populates="choice_group",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [Choice.workspace_id, Choice.choice_group_id],
        primaryjoin="and_(ChoiceGroup.workspace_id==Choice.workspace_id, ChoiceGroup.id==Choice.choice_group_id)",
    )


class Choice(Base):
    __tablename__ = "choices"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_choices_workspace_id_id"),
        Index("ix_choices_workspace_choice_group", "workspace_id", "choice_group_id"),
        Index("ix_choices_workspace_status", "workspace_id", "status"),
        ForeignKeyConstraint(
            ["workspace_id", "choice_group_id"],
            ["choice_groups.workspace_id", "choice_groups.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
        {"sqlite_autoincrement": True},
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    id: Mapped[str] = mapped_column(String(128), nullable=False)
    choice_group_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    patch: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    impact_preview: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False)

    choice_group: Mapped["ChoiceGroup"] = relationship(
        "ChoiceGroup",
        back_populates="choices",
        foreign_keys=[workspace_id, choice_group_id],
    )


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_issues_workspace_id_id"),
        Index("ix_issues_workspace_status", "workspace_id", "status"),
        Index("ix_issues_workspace_projection", "workspace_id", "suggested_projection"),
        Index("ix_issues_workspace_category", "workspace_id", "category"),
        {"sqlite_autoincrement": True},
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    id: Mapped[str] = mapped_column(String(128), nullable=False)
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


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_proposals_workspace_id_id"),
        Index("ix_proposals_workspace_status", "workspace_id", "status"),
        Index("ix_proposals_workspace_created_at", "workspace_id", "created_at"),
        {"sqlite_autoincrement": True},
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scope: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    patch: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    impact_preview: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    source: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="proposals")
