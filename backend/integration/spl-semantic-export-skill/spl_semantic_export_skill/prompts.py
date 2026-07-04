from __future__ import annotations

"""
Prompts templates for the SPL semantic conversion stages.
Outputs must strictly match the JSON schemas requested.
All natural language text, descriptions, reasons, and scenario details must be in Chinese.
All syntax identifiers, types, and field names must be in English.
"""

TYPE_NORMALIZATION_PROMPT = """
You are an expert DSL compiler translating a database-backed business object into a normalized SPL (Structured Prompt Language) Type definition.

[Input Business Object]
Name: {bo_name}
Description: {bo_description}
Attributes:
{bo_attributes}

[Instructions]
1. Generate a PascalCase English identifier name for the business object type as `type_name` (e.g., 'MaintenanceTask', 'DeviceArchive').
2. For each attribute, normalize its name to a camelCase English identifier as `normalized_name` (e.g., 'deviceCode', 'statusFlag').
3. Map the attribute's type to a valid SPL type (`text`, `number`, `boolean`, `List [text]`, `List [number]`, or another custom `Type` identifier like `TaskStatus`).
4. If an attribute represents a status, priority, or categorical field with discrete values (e.g. '处理中', '已完结'), flag it as `is_enum: true` and list the normalized English enum values in `enum_candidates` (e.g. ['pending', 'in_progress', 'completed']). If not, set `is_enum: false` and `enum_candidates: []`.
5. Keep the description and examples in Chinese.

[Output Format]
Your response must be a valid JSON object matching this schema:
{{
  "type_name": "PascalCaseEnglishTypeName",
  "fields": [
    {{
      "original_name": "original_attribute_name",
      "normalized_name": "camelCaseFieldName",
      "spl_type": "text | number | boolean | List [text] | List [number] | EnumTypeName",
      "is_enum": true,
      "enum_candidates": ["enum_value_1", "enum_value_2"],
      "description": "中文属性描述",
      "example": "属性值示例"
    }}
  ]
}}
"""

FLOW_TO_WORKER_PROMPT = """
You are a DSL compiler translating a RequirementSpace business flow into a structured SPL Worker.

[Input Flow]
Flow Name: {flow_name}
Description: {flow_description}

Flow Steps:
{flow_steps}

[Data Mapping Context]
The business objects and actors are normalized to the following SPL Type and Audience identifiers. You MUST reference these exact identifiers:
Types Mapping: {types_mapping}
Actors Mapping: {actors_mapping}

[Instructions]
1. Generate a PascalCase English name for the worker as `worker_name` (e.g., 'MaintainDeviceArchiveFlow').
2. Translate each flow step in order (sorted by position) into a structured step list.
3. For step types:
   - `systemAction`: The system performs an action. Map to `systemAction`.
   - `actorAction`: An actor performs an action. Map to `actorAction`.
   - `judgment`: A decision point. Map to `judgment`.
4. If step type is `judgment`, analyze the positive and negative paths in the flow description. Represent them as nested `sub_steps` with `branch_kind: "if"` and `branch_kind: "else"`. For sequential steps, `branch_kind` should be `sequential`.
5. Identify which normalized Type names are used as input variables (`inputs`) and output variables (`outputs`) of this worker.
6. Write all `command_text` and `decision_condition` values entirely in Chinese. Keep all keys and type references in English.

[Output Format]
Your response must be a valid JSON object matching this schema:
{{
  "worker_name": "PascalCaseWorkerName",
  "description": "中文业务流摘要",
  "actors": ["Actor_1", "Actor_2"],
  "inputs": ["NormalizedTypeName1"],
  "outputs": ["NormalizedTypeName2"],
  "main_flow_steps": [
    {{
      "source_step_id": 50,
      "step_type": "systemAction | actorAction | judgment",
      "command_text": "中文命令动作描述",
      "input_refs": ["NormalizedTypeName1"],
      "output_refs": ["NormalizedTypeName2"],
      "decision_condition": "中文判定条件(仅在judgment或分支中使用，否则为null)",
      "branch_kind": "sequential | if | else | elseif",
      "sub_steps": []
    }}
  ]
}}
"""

AC_TO_SCENARIO_PROMPT = """
You are a DSL compiler converting software acceptance criteria (AC) into structured SPL Gherkin scenarios.

[Input Feature Acceptance Criteria]
Feature Name: {feature_name}
Description: {feature_description}

Scenarios:
{scenarios}

[Instructions]
1. Parse each scenario and its Given/When/Then acceptance criteria.
2. Group each acceptance criterion into a clean scenario block.
3. Map the scenario to a `flow_type` of either `"normal"` (happy path), `"alternative"` (alternative flow), or `"exception"` (error case/validation error).
4. Parse the natural language criteria into structured list arrays: `given`, `when`, `then`.
5. Identify which original acceptance criteria IDs (e.g. 200, 201) are mapped to this scenario, and populate them in `source_acceptance_criterion_ids`.
6. Keep all scenario descriptions, Gherkin step texts, and validation notes entirely in Chinese. Keep keys in English.

[Output Format]
Your response must be a valid JSON object matching this schema:
{{
  "scenarios": [
    {{
      "source_scenario_id": 100,
      "source_acceptance_criterion_ids": [200, 201],
      "scenario_name": "中文场景名称",
      "flow_type": "normal | alternative | exception",
      "given": ["Given 前置条件描述 1", "Given 前置条件描述 2"],
      "when": ["When 触发动作描述"],
      "then": ["Then 系统响应与校验结果 1", "Then 系统响应与校验结果 2"]
    }}
  ]
}}
"""

COVERAGE_REVIEW_PROMPT = """
You are a quality assurance inspector checking the completeness and correctness of the compiled SPL specifications against the original requirements.

[Original Snapshot]
Features: {original_features}
Flows: {original_flows}
Business Objects: {original_business_objects}

[Generated SPL Intermediate Representation]
Types: {generated_types}
Workers: {generated_workers}

[Instructions]
1. Verify if all current-scope features are referenced or covered by the generated workers or scenarios.
2. Verify if all flows have corresponding workers.
3. Check for any semantic risks:
   - Are there judgment steps in flows that were translated as flat sequential commands instead of branching IF/ELSE statements?
   - Are there input/output parameters that reference missing or undeclared Type names?
   - Are there exclude/postponed features that were incorrectly included as active logic?
4. Generate the coverage report. Keep all comments, missing reasons, and semantic risks entirely in Chinese. Keep keys in English.

[Output Format]
Your response must be a valid JSON object matching this schema:
{{
  "coverage_passed": true,
  "covered_current_feature_ids": [10, 11],
  "missing_current_feature_ids": [],
  "unmapped_flow_ids": [],
  "unmapped_acceptance_criterion_ids": [],
  "semantic_risks": ["中文描述的语义风险与冲突检查，如：流程X中包含的判断步骤Y未能正确翻译为控制分支，退化为了常规COMMAND"]
}}
"""
