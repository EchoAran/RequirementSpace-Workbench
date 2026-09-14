from dataclasses import dataclass, field


@dataclass
class ActorIssueItem:
    actor_id: int
    name: str
    description: str


@dataclass
class FeatureIssueItem:
    feature_id: int
    name: str
    description: str
    actor_ids: list[int] = field(default_factory=list)
    parent_id: int | None = None
    child_ids: list[int] = field(default_factory=list)


@dataclass
class AcceptanceCriterionIssueItem:
    criterion_id: int
    content: str
    position: int


@dataclass
class ScenarioIssueItem:
    scenario_id: int
    feature_id: int
    actor_id: int
    name: str
    content: str
    acceptance_criteria_count: int = 0
    acceptance_criteria: list[AcceptanceCriterionIssueItem] = field(
        default_factory=list
    )


@dataclass
class DomainRuleIssueItem:
    rule_id: int
    logical_uuid: str
    title: str
    statement: str
    origin: str = "manual"
    confirmation_status: str = "confirmed"
    parent_rule_id: int | None = None


@dataclass
class RuleLinkIssueItem:
    link_id: int
    logical_uuid: str
    rule_id: int
    target_kind: str
    target_logical_uuid: str
    link_purpose: str


@dataclass
class FlowTransitionIssueItem:
    transition_id: int
    flow_id: int
    source_step_id: int
    target_step_id: int
    condition_text: str = ""
    label: str = ""
    is_default: bool = False
    position: int = 0
    semantic_tags: list[str] = field(default_factory=list)
    logical_uuid: str = ""


@dataclass
class FlowStepIssueItem:
    step_id: int
    flow_id: int
    position: int
    name: str
    description: str
    step_type: str
    actor_ids: list[int] = field(default_factory=list)
    input_business_object_ids: list[int] = field(default_factory=list)
    output_business_object_ids: list[int] = field(default_factory=list)
    logical_uuid: str = ""


@dataclass
class FlowIssueItem:
    flow_id: int
    name: str
    description: str
    confirmation_status: str = "ai_assumption"
    feature_ids: list[int] = field(default_factory=list)
    steps: list[FlowStepIssueItem] = field(default_factory=list)
    transitions: list[FlowTransitionIssueItem] = field(default_factory=list)
    logical_uuid: str = ""


@dataclass
class BusinessObjectIssueItem:
    business_object_id: int
    name: str
    description: str
    attribute_count: int = 0
    usage_count: int = 0


@dataclass
class ScopeIssueItem:
    scope_id: int
    feature_id: int
    status: str
    reason: str


@dataclass
class IssueProjectContext:
    project_id: int
    user_requirements: str
    actors: list[ActorIssueItem]
    features: list[FeatureIssueItem]
    scenarios: list[ScenarioIssueItem]
    flows: list[FlowIssueItem]
    business_objects: list[BusinessObjectIssueItem]
    scopes: list[ScopeIssueItem]
    domain_rules: list[DomainRuleIssueItem] = field(default_factory=list)
    rule_links: list[RuleLinkIssueItem] = field(default_factory=list)

    @property
    def leaf_features(self) -> list[FeatureIssueItem]:
        return [
            feature
            for feature in self.features
            if len(feature.child_ids) == 0
        ]
