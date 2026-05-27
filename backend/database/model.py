from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Column,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
    LargeBinary,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

from zoneinfo import ZoneInfo
BEIJING_TZ = ZoneInfo("Asia/Shanghai")

def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=beijing_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=beijing_now,
        onupdate=beijing_now,
        nullable=False,
    )

feature_actor_table = Table(
    "feature_actor",
    Base.metadata,
    Column(
        "feature_id",
        ForeignKey("features.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "actor_id",
        ForeignKey("actors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_feature_table = Table(
    "flow_feature",
    Base.metadata,
    Column(
        "flow_id",
        ForeignKey("flows.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "feature_id",
        ForeignKey("features.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_step_actor_table = Table(
    "flow_step_actor",
    Base.metadata,
    Column(
        "flow_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "actor_id",
        ForeignKey("actors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_step_input_business_object_table = Table(
    "flow_step_input_business_object",
    Base.metadata,
    Column(
        "flow_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "business_object_id",
        ForeignKey("business_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_step_output_business_object_table = Table(
    "flow_step_output_business_object",
    Base.metadata,
    Column(
        "flow_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "business_object_id",
        ForeignKey("business_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_step_next_table = Table(
    "flow_step_next",
    Base.metadata,
    Column(
        "source_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "target_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ProjectModel(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    user_requirements: Mapped[str] = mapped_column(Text, default="", nullable=False)

    perception_slot: Mapped[PerceptionSlotModel | None] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )
    perception_jobs: Mapped[list[PerceptionJobModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    actors: Mapped[list[ActorModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    features: Mapped[list[FeatureModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    scenarios: Mapped[list["ScenarioModel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    gherkin_specs: Mapped[list["GherkinSpecModel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    prototype_previews: Mapped[list["PrototypePreviewModel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    business_objects: Mapped[list[BusinessObjectModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    flows: Mapped[list[FlowModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    choice_groups: Mapped[list[ChoiceGroupModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list[AuditLogModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class PerceptionSlotModel(TimestampMixin, Base):
    __tablename__ = "perception_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    perception_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[ProjectModel] = relationship(back_populates="perception_slot")


class PerceptionJobModel(TimestampMixin, Base):
    __tablename__ = "perception_jobs"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "stage",
            "perception_kind",
            "target_type",
            "target_id",
            "context_hash",
            name="uq_perception_job_context",
        ),
        Index("ix_perception_jobs_project_stage", "project_id", "stage"),
        Index("ix_perception_jobs_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    perception_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(100),
        default="project",
        nullable=False,
    )
    target_id: Mapped[str] = mapped_column(
        String(255),
        default="",
        nullable=False,
    )
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    result_slot_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[ProjectModel] = relationship(back_populates="perception_jobs")


class ActorModel(TimestampMixin, Base):
    __tablename__ = "actors"
    __table_args__ = (
        Index("ix_actors_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[ProjectModel] = relationship(back_populates="actors")
    features: Mapped[list[FeatureModel]] = relationship(
        secondary=feature_actor_table,
        back_populates="actors",
    )
    scenarios: Mapped[list[ScenarioModel]] = relationship(back_populates="actor")
    gherkin_specs: Mapped[list["GherkinSpecModel"]] = relationship(
        back_populates="actor",
    )
    flow_steps: Mapped[list[FlowStepModel]] = relationship(
        secondary=flow_step_actor_table,
        back_populates="actors",
    )


class FeatureRelationModel(TimestampMixin, Base):
    __tablename__ = "feature_relations"
    __table_args__ = (
        UniqueConstraint(
            "parent_feature_id",
            "position",
            name="uq_feature_relation_parent_position",
        ),
        UniqueConstraint(
            "parent_feature_id",
            "child_feature_id",
            name="uq_feature_relation_parent_child",
        ),
        Index("ix_feature_relations_parent", "parent_feature_id"),
        Index("ix_feature_relations_child", "child_feature_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    parent_feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
    )

    child_feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    parent: Mapped["FeatureModel"] = relationship(
        "FeatureModel",
        foreign_keys=[parent_feature_id],
        back_populates="child_relations",
    )

    child: Mapped["FeatureModel"] = relationship(
        "FeatureModel",
        foreign_keys=[child_feature_id],
        back_populates="parent_relation",
    )


class FeatureModel(TimestampMixin, Base):
    __tablename__ = "features"
    __table_args__ = (
        Index("ix_features_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["ProjectModel"] = relationship(
        back_populates="features",
        foreign_keys=[project_id],
    )

    child_relations: Mapped[list["FeatureRelationModel"]] = relationship(
        "FeatureRelationModel",
        foreign_keys="FeatureRelationModel.parent_feature_id",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="FeatureRelationModel.position",
    )

    parent_relation: Mapped["FeatureRelationModel | None"] = relationship(
        "FeatureRelationModel",
        foreign_keys="FeatureRelationModel.child_feature_id",
        back_populates="child",
        uselist=False,
        passive_deletes=True,
    )

    actors: Mapped[list["ActorModel"]] = relationship(
        secondary=feature_actor_table,
        back_populates="features",
    )

    scenarios: Mapped[list["ScenarioModel"]] = relationship(
        back_populates="feature",
        cascade="all, delete-orphan",
    )
    gherkin_specs: Mapped[list["GherkinSpecModel"]] = relationship(
        back_populates="feature",
    )

    flows: Mapped[list["FlowModel"]] = relationship(
        secondary=flow_feature_table,
        back_populates="features",
    )

    scope: Mapped["ScopeModel | None"] = relationship(
        back_populates="feature",
        cascade="all, delete-orphan",
        uselist=False,
    )

class ScopeModel(TimestampMixin, Base):
    __tablename__ = "feature_scopes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False)

    positive_picture: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    negative_picture: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    positive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    feature: Mapped["FeatureModel"] = relationship(
        back_populates="scope",
    )

class ScenarioAcceptanceCriterionModel(TimestampMixin, Base):
    __tablename__ = "scenario_acceptance_criteria"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "position",
            name="uq_scenario_acceptance_position",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    scenario: Mapped["ScenarioModel"] = relationship(
        back_populates="acceptance_criteria",
    )


class GherkinSpecModel(TimestampMixin, Base):
    __tablename__ = "gherkin_specs"
    __table_args__ = (
        Index("ix_gherkin_specs_project_id", "project_id"),
        Index("ix_gherkin_specs_feature_id", "feature_id"),
        Index("ix_gherkin_specs_actor_id", "actor_id"),
        Index(
            "ix_gherkin_specs_project_feature_actor",
            "project_id",
            "feature_id",
            "actor_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"),
        nullable=False,
    )
    gherkin_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50),
        default="scenario_generation_skill",
        nullable=False,
    )

    project: Mapped[ProjectModel] = relationship(back_populates="gherkin_specs")
    feature: Mapped[FeatureModel] = relationship(back_populates="gherkin_specs")
    actor: Mapped[ActorModel] = relationship(back_populates="gherkin_specs")
    scenarios: Mapped[list["ScenarioModel"]] = relationship(
        back_populates="gherkin_spec",
    )


class PrototypePreviewModel(TimestampMixin, Base):
    __tablename__ = "prototype_previews"
    __table_args__ = (
        Index("ix_prototype_previews_project_id", "project_id"),
        Index("ix_prototype_previews_project_created", "project_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="ready",
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        default="placeholder",
        nullable=False,
    )
    html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    javascript: Mapped[str] = mapped_column(Text, default="", nullable=False)
    css: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    gherkin_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[ProjectModel] = relationship(
        back_populates="prototype_previews",
    )


class ScenarioModel(TimestampMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        Index("ix_scenarios_project_id", "project_id"),
        Index("ix_scenarios_feature_id", "feature_id"),
        Index("ix_scenarios_actor_id", "actor_id"),
        Index("ix_scenarios_gherkin_spec_id", "gherkin_spec_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    gherkin_spec_id: Mapped[int | None] = mapped_column(
        ForeignKey("gherkin_specs.id", ondelete="SET NULL"),
        nullable=True,
    )
    gherkin_scenario_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    project: Mapped[ProjectModel] = relationship(back_populates="scenarios")
    feature: Mapped[FeatureModel] = relationship(back_populates="scenarios")
    actor: Mapped[ActorModel] = relationship(back_populates="scenarios")
    gherkin_spec: Mapped[GherkinSpecModel | None] = relationship(
        back_populates="scenarios",
    )
    acceptance_criteria: Mapped[list[ScenarioAcceptanceCriterionModel]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioAcceptanceCriterionModel.position",
    )


class BusinessObjectModel(TimestampMixin, Base):
    __tablename__ = "business_objects"
    __table_args__ = (
        Index("ix_business_objects_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[ProjectModel] = relationship(back_populates="business_objects")
    attributes: Mapped[list[BusinessObjectAttributeModel]] = relationship(
        back_populates="business_object",
        cascade="all, delete-orphan",
    )
    input_flow_steps: Mapped[list[FlowStepModel]] = relationship(
        secondary=flow_step_input_business_object_table,
        back_populates="input_business_objects",
    )
    output_flow_steps: Mapped[list[FlowStepModel]] = relationship(
        secondary=flow_step_output_business_object_table,
        back_populates="output_business_objects",
    )


class BusinessObjectAttributeModel(TimestampMixin, Base):
    __tablename__ = "business_object_attributes"
    __table_args__ = (
        Index("ix_business_object_attributes_object_id", "business_object_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_object_id: Mapped[int] = mapped_column(
        ForeignKey("business_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    example: Mapped[str] = mapped_column(Text, default="", nullable=False)

    business_object: Mapped[BusinessObjectModel] = relationship(back_populates="attributes")


class FlowModel(TimestampMixin, Base):
    __tablename__ = "flows"
    __table_args__ = (
        Index("ix_flows_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[ProjectModel] = relationship(back_populates="flows")
    features: Mapped[list[FeatureModel]] = relationship(
        secondary=flow_feature_table,
        back_populates="flows",
    )
    steps: Mapped[list[FlowStepModel]] = relationship(
        back_populates="flow",
        cascade="all, delete-orphan",
        order_by="FlowStepModel.position",
    )


class FlowStepModel(TimestampMixin, Base):
    __tablename__ = "flow_steps"
    __table_args__ = (
        Index("ix_flow_steps_flow_id", "flow_id"),
        UniqueConstraint("flow_id", "position", name="uq_flow_step_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(
        ForeignKey("flows.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)

    flow: Mapped[FlowModel] = relationship(back_populates="steps")
    actors: Mapped[list[ActorModel]] = relationship(
        secondary=flow_step_actor_table,
        back_populates="flow_steps",
    )
    input_business_objects: Mapped[list[BusinessObjectModel]] = relationship(
        secondary=flow_step_input_business_object_table,
        back_populates="input_flow_steps",
    )
    output_business_objects: Mapped[list[BusinessObjectModel]] = relationship(
        secondary=flow_step_output_business_object_table,
        back_populates="output_flow_steps",
    )
    next_steps: Mapped[list[FlowStepModel]] = relationship(
        "FlowStepModel",
        secondary=flow_step_next_table,
        primaryjoin=lambda: FlowStepModel.id == flow_step_next_table.c.source_step_id,
        secondaryjoin=lambda: FlowStepModel.id == flow_step_next_table.c.target_step_id,
        back_populates="previous_steps",
    )
    previous_steps: Mapped[list[FlowStepModel]] = relationship(
        "FlowStepModel",
        secondary=flow_step_next_table,
        primaryjoin=lambda: FlowStepModel.id == flow_step_next_table.c.target_step_id,
        secondaryjoin=lambda: FlowStepModel.id == flow_step_next_table.c.source_step_id,
        back_populates="next_steps",
    )


class ChoiceGroupModel(TimestampMixin, Base):
    __tablename__ = "choice_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("perception_slots.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    selection_mode: Mapped[str] = mapped_column(String(50), default="single", nullable=False)

    project: Mapped[ProjectModel] = relationship(back_populates="choice_groups")
    choices: Mapped[list[ChoiceModel]] = relationship(
        back_populates="choice_group",
        cascade="all, delete-orphan",
    )


class ChoiceModel(TimestampMixin, Base):
    __tablename__ = "choices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    choice_group_id: Mapped[int] = mapped_column(
        ForeignKey("choice_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="candidate", nullable=False)
    patch: Mapped[dict] = mapped_column(JSON, nullable=False)
    impact_preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    choice_group: Mapped[ChoiceGroupModel] = relationship(back_populates="choices")


class AuditLogModel(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project: Mapped[ProjectModel] = relationship(back_populates="audit_logs")
