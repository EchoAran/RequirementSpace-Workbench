import json
from dataclasses import dataclass, field

from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.core.perceptrons.prompts import flows_perceive_prompt
from backend.schemas import FeatureNode, FlowNode


@dataclass
class FlowsPerceptronInput(PerceptronInput):
    """Input payload for flow perception analysis."""

    user_requirements: str
    features: list[FeatureNode]
    flows: list[FlowNode]
    domain_rules: list[dict] = field(default_factory=list)
    path_summaries: list[dict] = field(default_factory=list)
    scenarios: list[dict] = field(default_factory=list)


class FlowsPerceptron(BasePerceptron[FlowsPerceptronInput]):
    """Perceptron that analyzes flow coverage, transitions, and semantic continuity."""

    async def perceive(self, input_data: FlowsPerceptronInput) -> dict:
        """Analyze flows against requirements, features, domain rules, and path projections."""
        user_requirements_ = input_data.user_requirements

        leaf_features = [
            node for node in input_data.features if len(node.childrenIds) == 0
        ]
        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription", "actorIds"),
        ).dump(leaf_features)

        features_ = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2,
        )

        flows_payload = FlowNode.schema(
            many=True,
            only=(
                "flowId",
                "flowName",
                "flowDescription",
                "featureIds",
                "flowSteps.stepId",
                "flowSteps.stepName",
                "flowSteps.stepDescription",
                "flowSteps.stepType",
                "flowSteps.actorIds",
                "flowSteps.inputBusinessObjectIds",
                "flowSteps.outputBusinessObjectIds",
                "transitions.transitionId",
                "transitions.sourceStepId",
                "transitions.targetStepId",
                "transitions.label",
                "transitions.conditionText",
                "transitions.isDefault",
                "transitions.semanticTags",
            ),
        ).dump(input_data.flows)

        flow_context: dict[str, object] = {"flows": flows_payload}
        if input_data.domain_rules:
            flow_context["domain_rules"] = input_data.domain_rules
        if input_data.path_summaries:
            flow_context["path_projections"] = input_data.path_summaries
        if input_data.scenarios:
            flow_context["scenarios"] = input_data.scenarios

        flows_ = json.dumps(
            flow_context,
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=(
                flows_perceive_prompt
                .replace("{{user_requirements}}", user_requirements_)
                .replace("{{features}}", features_)
                .replace("{{flows}}", flows_)
            ),
            print_log=True,
            protected_inputs=self._protected_inputs(input_data),
        )

        return json.loads(response)
