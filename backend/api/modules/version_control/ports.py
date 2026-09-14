from abc import ABC, abstractmethod

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.model import (
    BranchWorkspaceModel,
    RequirementBranchModel,
    RequirementCommitModel,
)

# ==========================================
# Pydantic State Contract Schemas
# ==========================================

class ProjectMetadataState(BaseModel):
    user_requirements: str = Field(default="")
    kano_status: str = Field(default="missing")
    unlocked_stages: str = Field(default="")

class ActorState(BaseModel):
    logical_uuid: str
    name: str = Field(default="")
    description: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")

class FeatureState(BaseModel):
    logical_uuid: str
    name: str = Field(default="")
    description: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")
    actor_logical_uuids: list[str] = Field(default_factory=list)

class FeatureRelationState(BaseModel):
    logical_uuid: str
    parent_feature_logical_uuid: str
    child_feature_logical_uuid: str
    position: int = Field(default=0)

class ScenarioAcceptanceCriteriaState(BaseModel):
    logical_uuid: str
    position: int = Field(default=0)
    content: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")

class ScenarioState(BaseModel):
    logical_uuid: str
    feature_logical_uuid: str | None = None
    actor_logical_uuid: str | None = None
    name: str = Field(default="")
    content: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")
    acceptance_criteria: list[ScenarioAcceptanceCriteriaState] = Field(default_factory=list)

class BusinessObjectAttributeState(BaseModel):
    logical_uuid: str
    name: str = Field(default="")
    data_type: str = Field(default="")
    description: str = Field(default="")
    example: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")

class BusinessObjectState(BaseModel):
    logical_uuid: str
    name: str = Field(default="")
    description: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")
    attributes: list[BusinessObjectAttributeState] = Field(default_factory=list)

class FlowStepState(BaseModel):
    logical_uuid: str
    position: int = Field(default=0)
    name: str = Field(default="")
    description: str = Field(default="")
    step_type: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")
    actor_logical_uuids: list[str] = Field(default_factory=list)
    input_business_object_logical_uuids: list[str] = Field(default_factory=list)
    output_business_object_logical_uuids: list[str] = Field(default_factory=list)

class FlowTransitionState(BaseModel):
    logical_uuid: str
    source_step_logical_uuid: str
    target_step_logical_uuid: str
    label: str = Field(default="")
    condition_text: str = Field(default="")
    is_default: bool = Field(default=False)
    position: int = Field(default=0)
    semantic_tags: list[str] = Field(default_factory=list)
    origin: str = Field(default="manual")
    confirmation_status: str = Field(default="ai_assumption")

class FlowState(BaseModel):
    logical_uuid: str
    name: str = Field(default="")
    description: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")
    feature_logical_uuids: list[str] = Field(default_factory=list)
    steps: list[FlowStepState] = Field(default_factory=list)
    transitions: list[FlowTransitionState] = Field(default_factory=list)

class ScopeState(BaseModel):
    logical_uuid: str
    feature_logical_uuid: str | None = None
    status: str = Field(default="")
    positive_summary: str | None = None
    negative_summary: str | None = None
    reason: str = Field(default="")
    kano_category: str | None = None
    kano_category_name: str | None = None
    confirmation_status: str = Field(default="ai_assumption")

class DomainRuleState(BaseModel):
    logical_uuid: str
    parent_rule_logical_uuid: str | None = None
    title: str
    statement: str
    origin: str
    confirmation_status: str

class RuleLinkState(BaseModel):
    logical_uuid: str
    rule_logical_uuid: str
    target_kind: str
    target_logical_uuid: str
    link_purpose: str
    context_text: str = Field(default="")

class RequirementSpaceState(BaseModel):
    schema_version: str = Field(default="2.0")
    project_metadata: ProjectMetadataState
    actors: list[ActorState] = Field(default_factory=list)
    features: list[FeatureState] = Field(default_factory=list)
    feature_relations: list[FeatureRelationState] = Field(default_factory=list)
    scenarios: list[ScenarioState] = Field(default_factory=list)
    business_objects: list[BusinessObjectState] = Field(default_factory=list)
    flows: list[FlowState] = Field(default_factory=list)
    scopes: list[ScopeState] = Field(default_factory=list)
    domain_rules: list[DomainRuleState] = Field(default_factory=list)
    rule_links: list[RuleLinkState] = Field(default_factory=list)


# ==========================================
# Domain Ports & Repository Interfaces
# ==========================================

class IVersionControlRepository(ABC):
    @abstractmethod
    def get_branch(self, db: Session, branch_id: int) -> RequirementBranchModel | None:
        pass

    @abstractmethod
    def get_branch_by_name(self, db: Session, project_id: int, name: str) -> RequirementBranchModel | None:
        pass

    @abstractmethod
    def get_commit(self, db: Session, commit_id: int) -> RequirementCommitModel | None:
        pass

    @abstractmethod
    def get_commit_by_public_id(self, db: Session, public_id: str) -> RequirementCommitModel | None:
        pass

    @abstractmethod
    def get_workspace(self, db: Session, workspace_id: int) -> BranchWorkspaceModel | None:
        pass

    @abstractmethod
    def get_workspace_by_branch(self, db: Session, branch_id: int) -> BranchWorkspaceModel | None:
        pass


class IGitGraphValidator(ABC):
    @abstractmethod
    def validate_commit_parent(self, db: Session, commit_id: int, parent_commit_id: int) -> None:
        pass

    @abstractmethod
    def validate_branch_head(self, db: Session, branch_id: int, head_commit_id: int) -> None:
        pass


# ==========================================
# Concrete SQLAlchemy Implementations
# ==========================================

class SQLAlchemyVersionControlRepository(IVersionControlRepository):
    def get_branch(self, db: Session, branch_id: int) -> RequirementBranchModel | None:
        return db.get(RequirementBranchModel, branch_id)

    def get_branch_by_name(self, db: Session, project_id: int, name: str) -> RequirementBranchModel | None:
        from sqlalchemy import select
        return db.scalars(
            select(RequirementBranchModel).where(
                RequirementBranchModel.project_id == project_id,
                RequirementBranchModel.name == name
            )
        ).first()

    def get_commit(self, db: Session, commit_id: int) -> RequirementCommitModel | None:
        return db.get(RequirementCommitModel, commit_id)

    def get_commit_by_public_id(self, db: Session, public_id: str) -> RequirementCommitModel | None:
        from sqlalchemy import select
        return db.scalars(
            select(RequirementCommitModel).where(RequirementCommitModel.public_id == public_id)
        ).first()

    def get_workspace(self, db: Session, workspace_id: int) -> BranchWorkspaceModel | None:
        return db.get(BranchWorkspaceModel, workspace_id)

    def get_workspace_by_branch(self, db: Session, branch_id: int) -> BranchWorkspaceModel | None:
        from sqlalchemy import select
        return db.scalars(
            select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == branch_id)
        ).first()


class SQLAlchemyGitGraphValidator(IGitGraphValidator):
    def validate_commit_parent(self, db: Session, commit_id: int, parent_commit_id: int) -> None:
        from backend.database.model import (
            RequirementCommitModel,
            RequirementCommitParentModel,
        )
        if commit_id == parent_commit_id:
            raise ValueError("Commit cannot have itself as a parent (self-loop)")

        commit = db.get(RequirementCommitModel, commit_id)
        parent_commit = db.get(RequirementCommitModel, parent_commit_id)
        if commit and parent_commit and commit.project_id != parent_commit.project_id:
            raise ValueError("Parent and child commits must belong to the same project")

        visited = set()
        queue = [parent_commit_id]
        while queue:
            curr_id = queue.pop(0)
            if curr_id == commit_id:
                raise ValueError("Cycle detected in commit parent graph")
            if curr_id in visited:
                continue
            visited.add(curr_id)
            from sqlalchemy import select
            parents = db.execute(
                select(RequirementCommitParentModel.parent_commit_id).where(
                    RequirementCommitParentModel.commit_id == curr_id
                )
            ).scalars().all()
            queue.extend(parents)

    def validate_branch_head(self, db: Session, branch_id: int, head_commit_id: int) -> None:
        from backend.database.model import RequirementCommitModel
        branch = db.get(RequirementBranchModel, branch_id)
        commit = db.get(RequirementCommitModel, head_commit_id)
        if branch and commit and branch.project_id != commit.project_id:
            raise ValueError("Branch head commit must belong to the same project")
