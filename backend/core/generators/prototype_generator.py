from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.core.localized_messages import localized_message
from backend.core.prompt_resolver import get_content_locale
from backend.schemas import (
    ActorNode,
    BusinessObjectNode,
    FeatureNode,
    FlowNode,
    ScenarioNode,
)


@dataclass
class PrototypeGeneratorInput(GenerateInput):
    project_id: int
    project_name: str
    project_description: str
    user_requirements: str
    actors: list[ActorNode] = field(default_factory=list)
    features: list[FeatureNode] = field(default_factory=list)
    scenarios: list[ScenarioNode] = field(default_factory=list)
    business_objects: list[BusinessObjectNode] = field(default_factory=list)
    flows: list[FlowNode] = field(default_factory=list)
    gherkin_specs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PrototypePageGeneratorInput(GenerateInput):
    project_id: int
    project_name: str
    project_description: str
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: list[ScenarioNode] = field(default_factory=list)
    business_objects: list[BusinessObjectNode] = field(default_factory=list)
    flows: list[FlowNode] = field(default_factory=list)
    acceptance_criteria: dict[str, Any] = field(default_factory=dict)


class PrototypeGenerator(BaseGenerator[PrototypeGeneratorInput]):
    """Placeholder generator that mirrors the role-feature prototype contract."""

    async def generate(self, input_data: PrototypeGeneratorInput) -> dict[str, str]:
        actor = input_data.actors[0] if input_data.actors else ActorNode(
            actorId=0,
            actorName=localized_message("prototype_primary_user"),
            actorDescription=localized_message("prototype_default_user_description"),
        )
        feature = next(
            (item for item in input_data.features if not item.childrenIds),
            input_data.features[0] if input_data.features else FeatureNode(
                featureId=0,
                featureName=input_data.project_name or localized_message("prototype_feature"),
                featureDescription=input_data.project_description,
                actorIds=[actor.actorId],
                parentId=None,
                childrenIds=[],
            ),
        )
        return await self.generate_page(
            PrototypePageGeneratorInput(
                project_id=input_data.project_id,
                project_name=input_data.project_name,
                project_description=input_data.project_description,
                user_requirements=input_data.user_requirements,
                actor=actor,
                feature=feature,
                scenarios=input_data.scenarios,
                business_objects=input_data.business_objects,
                flows=input_data.flows,
                acceptance_criteria={"Features": []},
            )
        )

    async def generate_page(self, input_data: PrototypePageGeneratorInput) -> dict[str, str]:
        project_name = input_data.project_name or f"Project {input_data.project_id}"
        scenario_items = self._scenario_items(input_data.scenarios)
        data_items = self._business_object_items(input_data.business_objects)
        flow_items = self._flow_items(input_data.flows)

        html = f"""<!doctype html>
<html lang="{get_content_locale()}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(input_data.actor.actorName)} - {escape(input_data.feature.featureName)}</title>
  </head>
  <body>
    <main class="prototype-shell">
      <aside class="sidebar">
        <div class="brand">{escape(project_name)}</div>
        <div class="role-label">{localized_message('prototype_current_role')}</div>
        <h1>{escape(input_data.actor.actorName)}</h1>
        <p>{escape(input_data.actor.actorDescription)}</p>
      </aside>
      <section class="workspace">
        <header class="hero">
          <p class="eyebrow">{localized_message('prototype_role_feature')}</p>
          <h2>{escape(input_data.feature.featureName)}</h2>
          <p>{escape(input_data.feature.featureDescription or input_data.project_description or input_data.user_requirements)}</p>
        </header>
        <section class="surface">
          <div class="toolbar">
            <span>{localized_message('prototype_workspace', name=escape(input_data.actor.actorName))}</span>
            <button type="button">{localized_message('prototype_submit')}</button>
          </div>
          <div class="form-grid">
            <label>{localized_message('prototype_business_input')}<input placeholder="{localized_message('prototype_business_input_placeholder')}" /></label>
            <label>{localized_message('prototype_status')}<select><option>{localized_message('prototype_pending')}</option><option>{localized_message('prototype_completed')}</option></select></label>
            <label class="wide">{localized_message('prototype_notes')}<textarea placeholder="{localized_message('prototype_notes_placeholder')}"></textarea></label>
          </div>
        </section>
        <section class="split">
          <div class="panel">
            <h3>{localized_message('prototype_scenarios')}</h3>
            <ul>{scenario_items}</ul>
          </div>
          <div class="panel">
            <h3>{localized_message('prototype_business_data')}</h3>
            <ul>{data_items}</ul>
          </div>
        </section>
        <section class="panel">
          <h3>{localized_message('prototype_flow_touchpoints')}</h3>
          <ul>{flow_items}</ul>
        </section>
      </section>
    </main>
  </body>
</html>"""

        css = """
:root {
  color: #172026;
  background: #f4f7fb;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; }
.prototype-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 250px 1fr;
}
.sidebar {
  background: #13202f;
  color: white;
  padding: 24px;
}
.brand {
  font-size: 15px;
  font-weight: 800;
  margin-bottom: 32px;
}
.role-label, .eyebrow {
  color: #72d8c8;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .08em;
}
.sidebar h1 {
  font-size: 26px;
  line-height: 1.15;
}
.sidebar p {
  color: rgba(255,255,255,.72);
  line-height: 1.6;
}
.workspace {
  padding: 32px;
  display: grid;
  gap: 20px;
}
.hero h2 {
  margin: 6px 0 10px;
  font-size: 34px;
}
.hero p, li {
  color: #506175;
  line-height: 1.55;
}
.surface, .panel {
  background: white;
  border: 1px solid #dce5ef;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(22, 34, 51, .06);
}
.surface { padding: 18px; }
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #edf2f7;
  padding-bottom: 12px;
  margin-bottom: 16px;
  font-weight: 800;
}
button {
  border: 0;
  border-radius: 8px;
  background: #25b7a0;
  color: white;
  padding: 9px 14px;
  font-weight: 800;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
label {
  display: grid;
  gap: 6px;
  color: #607083;
  font-size: 12px;
  font-weight: 800;
}
.wide { grid-column: 1 / -1; }
input, select, textarea {
  width: 100%;
  border: 1px solid #dce5ef;
  border-radius: 8px;
  padding: 10px 12px;
  font: inherit;
}
textarea { min-height: 84px; resize: vertical; }
.panel { padding: 18px; }
.panel h3 { margin: 0 0 10px; }
.panel ul { padding-left: 18px; margin-bottom: 0; }
.split {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 760px) {
  .prototype-shell { grid-template-columns: 1fr; }
  .split, .form-grid { grid-template-columns: 1fr; }
}
"""

        javascript = f"""
document.querySelectorAll('button').forEach((button) => {{
  button.addEventListener('click', () => {{
    button.textContent = '{localized_message('prototype_submitted')}';
    window.setTimeout(() => {{ button.textContent = '{localized_message('prototype_submit')}'; }}, 1200);
  }});
}});
"""
        return {
            "HTML": html,
            "Javascript": javascript,
            "CSS": css,
        }

    @staticmethod
    def _scenario_items(scenarios: list[ScenarioNode]) -> str:
        if not scenarios:
            return f"<li>{localized_message('prototype_no_scenarios')}</li>"
        return "\n".join(
            f"<li><strong>{escape(scenario.scenarioName)}</strong>: {escape(scenario.scenarioContent)}</li>"
            for scenario in scenarios[:8]
        )

    @staticmethod
    def _flow_items(flows: list[FlowNode]) -> str:
        related_flows = [flow for flow in flows if flow.flowSteps]
        if not related_flows:
            return f"<li>{localized_message('prototype_no_flows')}</li>"
        return "\n".join(
            f"<li>{escape(flow.flowName)} ({len(flow.flowSteps)} steps)</li>"
            for flow in related_flows[:6]
        )

    @staticmethod
    def _business_object_items(business_objects: list[BusinessObjectNode]) -> str:
        if not business_objects:
            return f"<li>{localized_message('prototype_no_business_objects')}</li>"
        return "\n".join(
            f"<li>{escape(item.businessObjectName)} ({len(item.businessObjectAttributes)} fields)</li>"
            for item in business_objects[:6]
        )
