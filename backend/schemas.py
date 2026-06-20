from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

from dataclasses_json import dataclass_json, Undefined
from dataclasses_json import DataClassJsonMixin
import inflection

def node_dataclass(cls=None, **kwargs):
    """统一的结点类装饰器，支持传入额外参数覆盖默认配置"""
    def decorator(c):
        # 公共默认配置
        default_config = {
            "undefined": Undefined.EXCLUDE,
            "letter_case": inflection.underscore
        }
        final_config = {**default_config, **kwargs}     # 合并传入的自定义配置
        return dataclass_json(**final_config)(dataclass(c))     # 应用dataclass_json和dataclass装饰器
    if cls is None:
        return decorator
    return decorator(cls)

# 首先定义基础结点类
class BaseNode(DataClassJsonMixin):
    """所有结点的基础类"""
    pass

# 定义枚举类型
class ScopeStatus(str, Enum):
    """功能范围状态枚举"""
    CURRENT = "current"
    POSTPONED = "postponed"
    EXCLUDE = "exclude"

class FlowStepType(str, Enum):
    """流程步骤类型枚举"""
    ACTOR_ACTION = "actorAction"
    SYSTEM_ACTION = "systemAction"
    JUDGMENT = "judgment"

class PerceptionKindType(str, Enum):
    """感知槽对应的结点枚举"""
    ACTOR = "角色结点"
    FEATURE_BRANCH = "功能模块结点"
    FEATURE_LEAF = "功能叶子结点"
    SCENARIO = "场景结点"
    ACCEPTANCE_CRITERION = "成功标准结点"
    FLOW = "流程主结点"
    FLOW_STEP = "流程步骤结点"

# 角色结点
@node_dataclass
class ActorNode(BaseNode):
    kind: str = field(default="actor", init=False)

    actorId: int
    actorName: str
    actorDescription: str

# 成功标准
@node_dataclass
class AcceptanceCriterionNode(BaseNode):
    kind: str = field(default="acceptance_criterion", init=False)
    criterionId: int
    criterionContent: str

# 场景结点
@node_dataclass
class ScenarioNode(BaseNode):
    kind: str = field(default="scenario", init=False)

    scenarioId: int
    scenarioName: str
    scenarioContent: str  # 用户故事/场景描述
    featureId: int
    actorId: int
    acceptanceCriteria: List[AcceptanceCriterionNode] = field(default_factory=list)     # 空数组=没有验收条件

# 范围结点（kano分析结果）
@node_dataclass
class ScopeNode(BaseNode):
    kind: str = field(default="scope", init=False)
    scopeId: int
    scopeStatus: ScopeStatus
    reason: str

    positiveSummary: Optional[str] = None
    negativeSummary: Optional[str] = None
    positivePictureBase64: Optional[str] = None
    negativePictureBase64: Optional[str] = None
    kanoCategory: Optional[str] = None
    kanoCategoryName: Optional[str] = None

# 功能结点
@node_dataclass
class FeatureNode(BaseNode):
    kind: str = field(default="feature", init=False)

    featureId: int
    featureName: str
    featureDescription: str

    actorIds: List[int] = field(default_factory=list)  # 空数组=没有关联角色
    parentId: Optional[int] = None
    childrenIds: List[int] = field(default_factory=list)      # 空数组表示无子结点，即该结点为叶子

    scenarios: List[ScenarioNode] = field(default_factory=list)      # 空数组表示没有场景

    scope: Optional[ScopeNode] = None

# 业务对象属性结点
@node_dataclass
class BusinessObjectAttributeNode(BaseNode):
    kind: str = field(default="business_object_attribute", init=False)

    businessObjectAttributeId: int
    businessObjectAttributeName: str
    businessObjectAttributeDescription: str
    businessObjectAttributeType: str
    businessObjectAttributeExample: str

# 业务对象主结点
@node_dataclass
class BusinessObjectNode(BaseNode):
    kind: str = field(default="business_object", init=False)

    businessObjectId: int
    businessObjectName: str
    businessObjectDescription: str

    businessObjectAttributes: List[BusinessObjectAttributeNode] = field(default_factory=list)

# 流程步骤结点
@node_dataclass
class FlowStepNode(BaseNode):
    kind: str = field(default="flow_step", init=False)

    stepId: int
    stepName: str
    stepDescription: str

    stepType: FlowStepType

    actorIds: List[int] = field(default_factory=list)  # 空数组=没有
    inputBusinessObjectIds: List[int] = field(default_factory=list)  # 空数组=没有
    outputBusinessObjectIds: List[int] = field(default_factory=list)  # 空数组=没有

    nextStepIds: List[int] = field(default_factory=list)  # 空数组=没有

# 流程主结点
@node_dataclass
class FlowNode(BaseNode):
    kind: str = field(default="flow", init=False)

    flowId: int
    flowName: str
    flowDescription: str

    featureIds: List[int]  # 非空, 步骤必须关联至少一个功能

    flowSteps: List[FlowStepNode] = field(default_factory=list)

# 感知槽结点
@node_dataclass
class PerceptionSlot(BaseNode):
    kind: str = field(default="perception_slot", init=False)

    perceptionSlotId: int
    perceptionKind: PerceptionKindType
    perceptionDescription: str


class PerceptionJobStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    DONE_EMPTY = "done_empty"
    DONE_WITH_SLOT = "done_with_slot"
    FAILED = "failed"
    STALE = "stale"


@node_dataclass
class PerceptionJob(BaseNode):
    kind: str = field(default="perception_job", init=False)

    perceptionJobId: int
    projectId: int
    stage: str
    perceptionKind: str
    targetType: str
    targetId: Optional[str]
    contextHash: str
    status: PerceptionJobStatus
    resultSlot: Optional[PerceptionSlot] = None
    errorMessage: Optional[str] = None


class IssueSeverity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class IssueStage(str, Enum):
    WHAT = "what"
    HOW = "how"
    SCOPE = "scope"
    PREVIEW = "preview"


class FindingType(str, Enum):
    ISSUE = "issue"
    NEXT_SUGGESTION = "next_suggestion"
    GATE_CONDITION = "gate_condition"
    QUALITY_HINT = "quality_hint"


class BlockingScope(str, Enum):
    NONE = "none"
    STAGE_TRANSITION = "stage_transition"
    PREVIEW = "preview"
    EXPORT = "export"
    CHECKPOINT = "checkpoint"



@node_dataclass
class IssueTarget(BaseNode):
    kind: str = field(default="issue_target", init=False)

    targetType: str
    targetId: Optional[int | str] = None
    parentType: Optional[str] = None
    parentId: Optional[int | str] = None

    def key(self) -> str:
        parts = [
            self.targetType,
            str(self.targetId) if self.targetId is not None else "none",
        ]

        if self.parentType is not None:
            parts.extend(
                [
                    self.parentType,
                    str(self.parentId)
                    if self.parentId is not None
                    else "none",
                ]
            )

        return ":".join(parts)


@node_dataclass
class Issue(BaseNode):
    kind: str = field(default="issue", init=False)

    code: str
    stage: IssueStage
    severity: IssueSeverity
    title: str
    description: str
    target: Optional[IssueTarget] = None
    actionCode: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def issueId(self) -> str:
        target_key = self.target.key() if self.target is not None else "project"
        return f"{self.stage.value}:{self.code}:{target_key}"


@node_dataclass
class Finding(BaseNode):
    kind: str = field(default="finding", init=False)

    findingId: str
    type: FindingType
    stage: IssueStage
    code: str
    severity: IssueSeverity
    title: str
    description: str
    target: Optional[IssueTarget] = None
    blockingScope: BlockingScope = BlockingScope.NONE
    actionCode: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    capability: Optional[dict] = None



@node_dataclass
class IssueResolution(BaseNode):
    kind: str = field(default="issue_resolution", init=False)

    issueCode: str
    resolutionType: str
    title: str
    description: str
    action: dict
    draftId: Optional[str] = None
    draft: dict = field(default_factory=dict)
    patch: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "issue_code": self.issueCode,
            "resolution_type": self.resolutionType,
            "title": self.title,
            "description": self.description,
            "action": self.action,
            "draft_id": self.draftId,
            "draft": self.draft,
            "patch": self.patch,
        }


@node_dataclass
class NextSuggestion(BaseNode):
    kind: str = field(default="next_suggestion", init=False)

    sourceType: str
    code: str
    title: str
    description: str
    status: str = "ready"
    target: Optional[dict] = None
    action: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source_type": self.sourceType,
            "code": self.code,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "target": self.target,
            "action": self.action,
        }

# 原型预览
@node_dataclass
class PreviewUI(BaseNode):
    kind: str = field(default="preview_ui", init=False)
    prototypeId: int
    projectId: int
    html: str
    javascript: str
    css: str
    pages: List[dict] = field(default_factory=list)
    source: str = "placeholder"
    status: str = "ready"

@node_dataclass
class RequirementSpace(BaseNode):
    """需求空间，包含整个项目的所有需求信息"""
    kind: str = field(default="requirement_space", init=False)

    # 项目基本信息
    projectId: int
    projectName: str
    projectDescription: str
    userRequirements: str

    # 感知槽
    perceptionSlot: Optional[PerceptionSlot] = None  # None表示无感知槽

    # 所有类型的结点集合
    actors: List[ActorNode] = field(default_factory=list)
    features: List[FeatureNode] = field(default_factory=list)
    businessObjects: List[BusinessObjectNode] = field(default_factory=list)
    flows: List[FlowNode] = field(default_factory=list)
