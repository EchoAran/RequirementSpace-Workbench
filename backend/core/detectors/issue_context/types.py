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
    next_step_ids: list[int] = field(default_factory=list)


@dataclass
class FlowIssueItem:
    flow_id: int
    name: str
    description: str
    feature_ids: list[int] = field(default_factory=list)
    steps: list[FlowStepIssueItem] = field(default_factory=list)


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

    @property
    def leaf_features(self) -> list[FeatureIssueItem]:
        return [
            feature
            for feature in self.features
            if len(feature.child_ids) == 0
        ]
