from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeKind(str, Enum):
    GOAL = "goal"
    CAPABILITY = "capability"
    ACTOR = "actor"
    TASK = "task"
    FLOW = "flow"
    FLOW_STEP = "flow_step"
    RULE = "rule"
    BUSINESS_OBJECT = "business_object"
    FIELD = "field"
    STATE_MACHINE = "state_machine"
    OBJECT_STATE = "object_state"
    STATE_TRANSITION = "state_transition"
    SCREEN = "screen"
    UI_COMPONENT = "ui_component"


class NodeStatus(str, Enum):
    AI_ASSUMPTION = "ai_assumption"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CONFIRMED = "confirmed"
    CONFLICT = "conflict"
    DEFERRED = "deferred"
    EXCLUDED = "excluded"


class ScopeStatus(str, Enum):
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    EXTERNAL_DEPENDENCY = "external_dependency"
    DEFERRED = "deferred"


class LinkType(str, Enum):
    REALIZES = "realizes"
    SUPPORTS = "supports"
    PERFORMED_BY = "performed_by"
    OWNS = "owns"
    PRECEDES = "precedes"
    BRANCHES_TO = "branches_to"
    GUARDS = "guards"
    READS = "reads"
    WRITES = "writes"
    CHANGES_STATE = "changes_state"
    CONTAINS = "contains"
    ACCESSIBLE_BY = "accessible_by"
    BINDS_FIELD = "binds_field"
    INVOKES_STEP = "invokes_step"
    DEPENDS_ON = "depends_on"
    DIAGNOSES = "diagnoses"


class ProjectionKind(str, Enum):
    GOAL = "goal"
    ROLE = "role"
    SYSTEM = "system"
    DATA = "data"
    UI = "ui"


class SlotStatus(str, Enum):
    EMPTY = "empty"
    EXPANDING = "expanding"
    CANDIDATE_READY = "candidate_ready"
    FILLED = "filled"
    DEFERRED = "deferred"


class ChoiceStatus(str, Enum):
    CANDIDATE = "candidate"
    SELECTED = "selected"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class IssueStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class LinkStatus(str, Enum):
    ACTIVE = "active"
    SUSPECTED = "suspected"
    INVALID = "invalid"


class ChoiceGroupStatus(str, Enum):
    OPEN = "open"
    SELECTED = "selected"
    DISMISSED = "dismissed"


class SlotArity(str, Enum):
    ONE = "one"
    MANY = "many"


class SelectionMode(str, Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IssueCategory(str, Enum):
    MISSING = "missing"
    CONFLICT = "conflict"
    AMBIGUITY = "ambiguity"
    SCOPE_RISK = "scope_risk"
    FLOW_GAP = "flow_gap"
    DATA_GAP = "data_gap"
    UI_GAP = "ui_gap"
    RULE_GAP = "rule_gap"


class SourceType(str, Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"
    TEMPLATE = "template"
    IMPORTED = "imported"


class CapabilityPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActorRoleType(str, Enum):
    PRIMARY_USER = "primary_user"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN = "admin"
    EXTERNAL = "external"


class FlowStepType(str, Enum):
    USER_ACTION = "user_action"
    SYSTEM_ACTION = "system_action"
    DECISION = "decision"
    NOTIFICATION = "notification"
    STATE_TRANSITION = "state_transition"
    EXTERNAL_CALL = "external_call"
    MANUAL_OPERATION = "manual_operation"


class RuleType(str, Enum):
    CONDITION = "condition"
    VALIDATION = "validation"
    PERMISSION = "permission"
    BUSINESS_POLICY = "business_policy"
    CALCULATION = "calculation"


class FieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    ENUM = "enum"
    FILE = "file"
    REFERENCE = "reference"


class ValueSource(str, Enum):
    USER_INPUT = "user_input"
    SYSTEM_GENERATED = "system_generated"
    EXTERNAL = "external"


class UIComponentType(str, Enum):
    FORM = "form"
    TABLE = "table"
    DETAIL = "detail"
    LIST = "list"
    BUTTON = "button"
    FIELD = "field"
    STATUS_BADGE = "status_badge"
    DIALOG = "dialog"
    NAVIGATION = "navigation"


class SourceRecord(StrictModel):
    type: SourceType
    text: str | None = None
    refId: str | None = None
    confidence: float | None = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not 0 <= value <= 1:
            raise ValueError("confidence 必须在 0 到 1 之间")
        return value


class Assumption(StrictModel):
    id: str = Field(min_length=1)
    description: str = ""


class Meta(StrictModel):
    domain: str | None = None
    taskType: str | None = None
    templateId: str | None = None
    inputPrompt: str | None = None
    assumptions: list[Assumption] = Field(default_factory=list)


class BaseNode(StrictModel):
    id: str = Field(min_length=1)
    kind: NodeKind
    title: str = Field(min_length=1)
    description: str = ""
    status: NodeStatus
    scopeStatus: ScopeStatus | None = None
    confidence: float | None = None
    source: SourceRecord
    tags: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not 0 <= value <= 1:
            raise ValueError("confidence 必须在 0 到 1 之间")
        return value


class GoalNode(BaseNode):
    kind: Literal[NodeKind.GOAL]
    successCriteria: list[str] = Field(default_factory=list)


class CapabilityNode(BaseNode):
    kind: Literal[NodeKind.CAPABILITY]
    priority: CapabilityPriority | None = None
    acceptanceNotes: list[str] = Field(default_factory=list)


class ActorNode(BaseNode):
    kind: Literal[NodeKind.ACTOR]
    roleType: ActorRoleType | None = None
    responsibilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class TaskNode(BaseNode):
    kind: Literal[NodeKind.TASK]
    outcome: str | None = None


class FlowNode(BaseNode):
    kind: Literal[NodeKind.FLOW]
    trigger: str | None = None


class FlowStepNode(BaseNode):
    kind: Literal[NodeKind.FLOW_STEP]
    stepType: FlowStepType | None = None


class RuleNode(BaseNode):
    kind: Literal[NodeKind.RULE]
    ruleType: RuleType | None = None
    expression: str | None = None
    naturalLanguage: str | None = None


class BusinessObjectNode(BaseNode):
    kind: Literal[NodeKind.BUSINESS_OBJECT]


class FieldNode(BaseNode):
    kind: Literal[NodeKind.FIELD]
    fieldType: FieldType | None = None
    required: bool | None = None
    valueSource: ValueSource | None = None


class StateMachineNode(BaseNode):
    kind: Literal[NodeKind.STATE_MACHINE]


class ObjectStateNode(BaseNode):
    kind: Literal[NodeKind.OBJECT_STATE]


class StateTransitionNode(BaseNode):
    kind: Literal[NodeKind.STATE_TRANSITION]


class ScreenNode(BaseNode):
    kind: Literal[NodeKind.SCREEN]
    purpose: str | None = None
    route: str | None = None


class UIComponentNode(BaseNode):
    kind: Literal[NodeKind.UI_COMPONENT]
    componentType: UIComponentType | None = None


RequirementNode = Annotated[
    GoalNode
    | CapabilityNode
    | ActorNode
    | TaskNode
    | FlowNode
    | FlowStepNode
    | RuleNode
    | BusinessObjectNode
    | FieldNode
    | StateMachineNode
    | ObjectStateNode
    | StateTransitionNode
    | ScreenNode
    | UIComponentNode,
    Field(discriminator="kind"),
]


class RequirementLink(StrictModel):
    id: str = Field(min_length=1)
    sourceId: str = Field(min_length=1)
    targetId: str = Field(min_length=1)
    type: LinkType
    label: str | None = None
    status: LinkStatus = LinkStatus.ACTIVE
    source: SourceRecord


class SlotContext(StrictModel):
    projectionHints: list[ProjectionKind] = Field(default_factory=list)
    relatedNodeIds: list[str] = Field(default_factory=list)
    promptHints: list[str] = Field(default_factory=list)


class RequirementSlot(StrictModel):
    id: str = Field(min_length=1)
    ownerNodeId: str = Field(min_length=1)
    ownerProjection: ProjectionKind
    name: str = Field(min_length=1)
    description: str = ""
    expectedKinds: list[NodeKind] = Field(default_factory=list)
    arity: SlotArity = SlotArity.MANY
    status: SlotStatus = SlotStatus.EMPTY
    context: SlotContext = Field(default_factory=SlotContext)


class ImpactPreview(StrictModel):
    affectedGoals: list[str] = Field(default_factory=list)
    affectedActors: list[str] = Field(default_factory=list)
    affectedFlows: list[str] = Field(default_factory=list)
    affectedObjects: list[str] = Field(default_factory=list)
    affectedScreens: list[str] = Field(default_factory=list)
    newIssues: list[str] | None = None
    resolvedIssues: list[str] | None = None


class NodeUpdate(StrictModel):
    id: str = Field(min_length=1)
    title: str | None = None
    description: str | None = None
    status: NodeStatus | None = None
    scopeStatus: ScopeStatus | None = None
    confidence: float | None = None
    source: SourceRecord | None = None
    tags: list[str] | None = None
    successCriteria: list[str] | None = None
    priority: CapabilityPriority | None = None
    acceptanceNotes: list[str] | None = None
    roleType: ActorRoleType | None = None
    responsibilities: list[str] | None = None
    permissions: list[str] | None = None
    outcome: str | None = None
    trigger: str | None = None
    stepType: FlowStepType | None = None
    ruleType: RuleType | None = None
    expression: str | None = None
    naturalLanguage: str | None = None
    fieldType: FieldType | None = None
    required: bool | None = None
    valueSource: ValueSource | None = None
    purpose: str | None = None
    route: str | None = None
    componentType: UIComponentType | None = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not 0 <= value <= 1:
            raise ValueError("confidence 必须在 0 到 1 之间")
        return value


class LinkUpdate(StrictModel):
    id: str = Field(min_length=1)
    sourceId: str | None = None
    targetId: str | None = None
    type: LinkType | None = None
    label: str | None = None
    status: LinkStatus | None = None
    source: SourceRecord | None = None


class SlotUpdate(StrictModel):
    id: str = Field(min_length=1)
    ownerNodeId: str | None = None
    ownerProjection: ProjectionKind | None = None
    name: str | None = None
    description: str | None = None
    expectedKinds: list[NodeKind] | None = None
    arity: SlotArity | None = None
    status: SlotStatus | None = None
    context: SlotContext | None = None


class Issue(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    severity: Severity = Severity.MEDIUM
    category: IssueCategory = IssueCategory.MISSING
    relatedNodeIds: list[str] = Field(default_factory=list)
    suggestedProjection: ProjectionKind
    suggestedAction: str = ""
    status: IssueStatus = IssueStatus.OPEN
    source: SourceRecord


class IssueUpdate(StrictModel):
    id: str = Field(min_length=1)
    title: str | None = None
    description: str | None = None
    severity: Severity | None = None
    category: IssueCategory | None = None
    relatedNodeIds: list[str] | None = None
    suggestedProjection: ProjectionKind | None = None
    suggestedAction: str | None = None
    status: IssueStatus | None = None
    source: SourceRecord | None = None


class Choice(StrictModel):
    id: str = Field(min_length=1)
    choiceGroupId: str = Field(min_length=1)
    title: str = Field(min_length=1)
    rationale: str = ""
    patch: GraphPatch = Field(default_factory=lambda: GraphPatch())
    impactPreview: ImpactPreview = Field(default_factory=ImpactPreview)
    status: ChoiceStatus = ChoiceStatus.CANDIDATE


class ChoicePatch(StrictModel):
    id: str = Field(min_length=1)
    title: str | None = None
    rationale: str | None = None
    patch: GraphPatch | None = None
    impactPreview: ImpactPreview | None = None
    status: ChoiceStatus | None = None


class ChoiceGroup(StrictModel):
    id: str = Field(min_length=1)
    slotId: str = Field(min_length=1)
    choices: list[Choice] = Field(default_factory=list)
    selectedChoiceIds: list[str] = Field(default_factory=list)
    selectionMode: SelectionMode = SelectionMode.SINGLE
    status: ChoiceGroupStatus = ChoiceGroupStatus.OPEN

    @field_validator("selectedChoiceIds")
    @classmethod
    def validate_selected_choice_ids(cls, value: list[str], info) -> list[str]:
        selection_mode = info.data.get("selectionMode")
        if selection_mode == SelectionMode.SINGLE and len(value) > 1:
            raise ValueError("single 模式下 selectedChoiceIds 最多只能有 1 个")
        return value


class ChoiceGroupUpdate(StrictModel):
    id: str = Field(min_length=1)
    slotId: str | None = None
    choices: list[ChoicePatch] | None = None
    selectedChoiceIds: list[str] | None = None
    selectionMode: SelectionMode | None = None
    status: ChoiceGroupStatus | None = None


class Proposal(StrictModel):
    id: str = Field(min_length=1)
    workspaceId: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = ""
    scope: dict[str, object] = Field(default_factory=dict)
    patch: GraphPatch = Field(default_factory=lambda: GraphPatch())
    impactPreview: ImpactPreview = Field(default_factory=ImpactPreview)
    status: ProposalStatus = ProposalStatus.DRAFT
    createdAt: str = Field(min_length=1)
    source: SourceRecord


class GoalProjectionState(StrictModel):
    expandedNodeIds: list[str] = Field(default_factory=list)
    filters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    layout: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class RoleProjectionState(StrictModel):
    activeActorId: str | None = None
    filters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    layout: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SystemProjectionState(StrictModel):
    swimlaneBy: Literal["actor", "system"] = "actor"
    highlightedNodeIds: list[str] = Field(default_factory=list)
    filters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    layout: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class DataProjectionState(StrictModel):
    showFields: bool = True
    showStates: bool = True
    filters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    layout: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class UIProjectionState(StrictModel):
    activeActorId: str | None = None
    activeScreenId: str | None = None
    filters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    layout: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ProjectionState(StrictModel):
    goal: GoalProjectionState = Field(default_factory=GoalProjectionState)
    role: RoleProjectionState = Field(default_factory=RoleProjectionState)
    system: SystemProjectionState = Field(default_factory=SystemProjectionState)
    data: DataProjectionState = Field(default_factory=DataProjectionState)
    ui: UIProjectionState = Field(default_factory=UIProjectionState)


class OperationActor(StrictModel):
    type: SourceType
    refId: str | None = None


class OperationRecord(StrictModel):
    id: str = Field(min_length=1)
    actionType: str = Field(min_length=1)
    targetIds: list[str] = Field(default_factory=list)
    actor: OperationActor
    summary: str = ""
    details: dict[str, object] = Field(default_factory=dict)
    timestamp: str = Field(min_length=1)


class AuditInfo(StrictModel):
    createdAt: str = ""
    updatedAt: str = ""
    sourceSummary: list[SourceRecord] = Field(default_factory=list)
    operationLog: list[OperationRecord] = Field(default_factory=list)


class GraphPatch(StrictModel):
    addNodes: list[RequirementNode] = Field(default_factory=list)
    updateNodes: list[NodeUpdate] = Field(default_factory=list)
    removeNodeIds: list[str] = Field(default_factory=list)
    addLinks: list[RequirementLink] = Field(default_factory=list)
    updateLinks: list[LinkUpdate] = Field(default_factory=list)
    removeLinkIds: list[str] = Field(default_factory=list)
    addSlots: list[RequirementSlot] = Field(default_factory=list)
    updateSlots: list[SlotUpdate] = Field(default_factory=list)
    removeSlotIds: list[str] = Field(default_factory=list)
    addChoiceGroups: list[ChoiceGroup] = Field(default_factory=list)
    updateChoiceGroups: list[ChoiceGroupUpdate] = Field(default_factory=list)
    addIssues: list[Issue] = Field(default_factory=list)
    updateIssues: list[IssueUpdate] = Field(default_factory=list)
    resolveIssueIds: list[str] = Field(default_factory=list)


class RequirementSpaceIR(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    idea: str = ""
    meta: Meta = Field(default_factory=Meta)
    nodes: dict[str, RequirementNode] = Field(default_factory=dict)
    links: list[RequirementLink] = Field(default_factory=list)
    slots: dict[str, RequirementSlot] = Field(default_factory=dict)
    choiceGroups: dict[str, ChoiceGroup] = Field(default_factory=dict)
    proposals: dict[str, Proposal] = Field(default_factory=dict)
    issues: dict[str, Issue] = Field(default_factory=dict)
    projections: ProjectionState = Field(default_factory=ProjectionState)
    audit: AuditInfo = Field(default_factory=AuditInfo)


Choice.model_rebuild()
ChoicePatch.model_rebuild()
ChoiceGroup.model_rebuild()
ChoiceGroupUpdate.model_rebuild()
Proposal.model_rebuild()
GraphPatch.model_rebuild()
