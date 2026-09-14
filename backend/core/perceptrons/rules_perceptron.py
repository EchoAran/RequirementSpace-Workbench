import json
from dataclasses import dataclass, field

from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.core.perceptrons.prompts import rules_perceive_prompt


@dataclass
class RulePerceptronInput(PerceptronInput):
    """Input payload for domain rule perception analysis."""

    user_requirements: str
    domain_rules: list[dict] = field(default_factory=list)
    rule_links: list[dict] = field(default_factory=list)
    flows: list[dict] = field(default_factory=list)
    scenarios: list[dict] = field(default_factory=list)


class RulePerceptron(BasePerceptron[RulePerceptronInput]):
    """Perceptron that analyzes domain rules for contradictions, ambiguities, and coverage."""

    async def perceive(self, input_data: RulePerceptronInput) -> dict:
        """Analyze domain rule consistency and completeness against requirements and flows."""
        rules_text = json.dumps(
            {"domain_rules": input_data.domain_rules},
            ensure_ascii=False,
            indent=2,
        )
        links_text = json.dumps(
            {"rule_links": input_data.rule_links},
            ensure_ascii=False,
            indent=2,
        )
        flows_text = json.dumps(
            {"flows": input_data.flows},
            ensure_ascii=False,
            indent=2,
        )
        scenarios_text = json.dumps(
            {"scenarios": input_data.scenarios},
            ensure_ascii=False,
            indent=2,
        )

        prompt = (
            rules_perceive_prompt
            .replace("{{user_requirements}}", input_data.user_requirements)
            .replace("{{domain_rules}}", rules_text)
            .replace("{{rule_links}}", links_text)
            .replace("{{flows}}", flows_text)
            .replace("{{scenarios}}", scenarios_text)
        )

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            print_log=True,
            protected_inputs=self._protected_inputs(input_data),
        )

        return json.loads(response)
