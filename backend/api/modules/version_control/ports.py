from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.model import (
    RequirementBranchModel,
    RequirementCommitModel,
    BranchWorkspaceModel,
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
    actor_logical_uuids: List[str] = Field(default_factory=list)

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
    feature_logical_uuid: Optional[str] = None
    actor_logical_uuid: Optional[str] = None
    name: str = Field(default="")
    content: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")
    acceptance_criteria: List[ScenarioAcceptanceCriteriaState] = Field(default_factory=list)

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
    attributes: List[BusinessObjectAttributeState] = Field(default_factory=list)

class FlowStepState(BaseModel):
    logical_uuid: str
    position: int = Field(default=0)
    name: str = Field(default="")
    description: str = Field(default="")
    step_type: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")
    actor_logical_uuids: List[str] = Field(default_factory=list)
    input_business_object_logical_uuids: List[str] = Field(default_factory=list)
    output_business_object_logical_uuids: List[str] = Field(default_factory=list)
    next_step_logical_uuids: List[str] = Field(default_factory=list)

class FlowState(BaseModel):
    logical_uuid: str
    name: str = Field(default="")
    description: str = Field(default="")
    confirmation_status: str = Field(default="ai_assumption")
    feature_logical_uuids: List[str] = Field(default_factory=list)
    steps: List[FlowStepState] = Field(default_factory=list)

class ScopeState(BaseModel):
    logical_uuid: str
    feature_logical_uuid: Optional[str] = None
    status: str = Field(default="")
    positive_summary: Optional[str] = None
    negative_summary: Optional[str] = None
    reason: str = Field(default="")
    kano_category: Optional[str] = None
    kano_category_name: Optional[str] = None
    confirmation_status: str = Field(default="ai_assumption")

class RequirementSpaceState(BaseModel):
    schema_version: str = Field(default="1.0")
    project_metadata: ProjectMetadataState
    actors: List[ActorState] = Field(default_factory=list)
    features: List[FeatureState] = Field(default_factory=list)
    feature_relations: List[FeatureRelationState] = Field(default_factory=list)
    scenarios: List[ScenarioState] = Field(default_factory=list)
    business_objects: List[BusinessObjectState] = Field(default_factory=list)
    flows: List[FlowState] = Field(default_factory=list)
    scopes: List[ScopeState] = Field(default_factory=list)


# ==========================================
# Domain Ports & Repository Interfaces
# ==========================================

class IVersionControlRepository(ABC):
    @abstractmethod
    def get_branch(self, db: Session, branch_id: int) -> Optional[RequirementBranchModel]:
        pass

    @abstractmethod
    def get_branch_by_name(self, db: Session, project_id: int, name: str) -> Optional[RequirementBranchModel]:
        pass

    @abstractmethod
    def get_commit(self, db: Session, commit_id: int) -> Optional[RequirementCommitModel]:
        pass

    @abstractmethod
    def get_commit_by_public_id(self, db: Session, public_id: str) -> Optional[RequirementCommitModel]:
        pass

    @abstractmethod
    def get_workspace(self, db: Session, workspace_id: int) -> Optional[BranchWorkspaceModel]:
        pass

    @abstractmethod
    def get_workspace_by_branch(self, db: Session, branch_id: int) -> Optional[BranchWorkspaceModel]:
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
    def get_branch(self, db: Session, branch_id: int) -> Optional[RequirementBranchModel]:
        return db.get(RequirementBranchModel, branch_id)

    def get_branch_by_name(self, db: Session, project_id: int, name: str) -> Optional[RequirementBranchModel]:
        from sqlalchemy import select
        return db.scalars(
            select(RequirementBranchModel).where(
                RequirementBranchModel.project_id == project_id,
                RequirementBranchModel.name == name
            )
        ).first()

    def get_commit(self, db: Session, commit_id: int) -> Optional[RequirementCommitModel]:
        return db.get(RequirementCommitModel, commit_id)

    def get_commit_by_public_id(self, db: Session, public_id: str) -> Optional[RequirementCommitModel]:
        from sqlalchemy import select
        return db.scalars(
            select(RequirementCommitModel).where(RequirementCommitModel.public_id == public_id)
        ).first()

    def get_workspace(self, db: Session, workspace_id: int) -> Optional[BranchWorkspaceModel]:
        return db.get(BranchWorkspaceModel, workspace_id)

    def get_workspace_by_branch(self, db: Session, branch_id: int) -> Optional[BranchWorkspaceModel]:
        from sqlalchemy import select
        return db.scalars(
            select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == branch_id)
        ).first()


class SQLAlchemyGitGraphValidator(IGitGraphValidator):
    def validate_commit_parent(self, db: Session, commit_id: int, parent_commit_id: int) -> None:
        from backend.database.model import RequirementCommitParentModel, RequirementCommitModel
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
