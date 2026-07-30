def _feature_tree_lines(features, tr) -> list[str]:
    lines = []

    def append_children(parent_id=None, level=0):
        for feature in features:
            if feature.parent_id != parent_id:
                continue
            scope_text = ""
            if feature.scope:
                status_map = {
                    "current": tr("markdown_scope_current"),
                    "postponed": tr("markdown_scope_postponed"),
                    "exclude": tr("markdown_scope_exclude"),
                }
                raw_status = feature.scope.scope_status or ""
                status_text = status_map.get(
                    raw_status.lower(),
                    raw_status,
                )
                scope_text = (
                    f" [{tr('markdown_scope')}: {status_text}]"
                )
            lines.append(
                f"{'  ' * level}- **{feature.feature_name}**: "
                f"{feature.feature_description}{scope_text}"
            )
            append_children(feature.feature_id, level + 1)

    append_children()
    return lines


def build_feature_markdown_lines(detail, tr) -> list[str]:
    lines = [f"## 4. {tr('markdown_features')}"]
    if not detail.features:
        lines.append(tr("markdown_no_features"))
    else:
        lines.append(f"### 4.1 {tr('markdown_feature_tree')}")
        lines.extend(_feature_tree_lines(detail.features, tr))
        lines.append("")
        lines.append(f"### 4.2 {tr('markdown_scenarios')}")
        has_scenarios = False
        for feature in detail.features:
            if not feature.scenarios:
                continue
            has_scenarios = True
            lines.append(
                f"#### {tr('markdown_module')}: "
                f"{feature.feature_name}"
            )
            for scenario in feature.scenarios:
                lines.append(
                    f"- **{tr('markdown_scenario')}: "
                    f"{scenario.scenario_name}**"
                )
                lines.append(
                    f"  - *{tr('markdown_user_story')}*: "
                    f"{scenario.scenario_content}"
                )
                if scenario.acceptance_criteria:
                    lines.append(
                        f"  - *{tr('markdown_acceptance_criteria')}*:"
                    )
                    for criterion in scenario.acceptance_criteria:
                        lines.append(
                            f"    - [ ] {criterion.criterion_content}"
                        )
            lines.append("")
        if not has_scenarios:
            lines.append(tr("markdown_no_scenarios"))
    lines.extend(["", "---", ""])
    return lines


def _business_object_lines(detail, tr) -> list[str]:
    lines = [f"### 5.1 {tr('markdown_business_objects')}"]
    if not detail.business_objects:
        lines.append(tr("markdown_no_business_objects"))
    else:
        for business_object in detail.business_objects:
            lines.append(
                f"#### {tr('markdown_entity')}: "
                f"{business_object.business_object_name}"
            )
            lines.append(
                f"- *{tr('markdown_object_description')}*: "
                f"{business_object.business_object_description}"
            )
            if business_object.business_object_attributes:
                lines.append("")
                lines.append(tr("markdown_attribute_header"))
                lines.append("| --- | --- | --- | --- |")
                for attribute in (
                    business_object.business_object_attributes
                ):
                    lines.append(
                        "| "
                        f"{attribute.business_object_attribute_name} | "
                        f"{attribute.business_object_attribute_description} | "
                        f"{attribute.business_object_attribute_type} | "
                        f"{attribute.business_object_attribute_example} |"
                    )
            else:
                lines.append(
                    f"- *{tr('markdown_no_attributes')}*"
                )
            lines.append("")
    lines.append("")
    return lines


def _flow_step_lines(
    step,
    tr,
    actor_names: dict[int, str],
    business_object_names: dict[int, str],
) -> list[str]:
    lines = [
        f"- **{tr('markdown_step')}: {step.step_name}** "
        f"({step.step_type})",
        f"  - *{tr('markdown_description')}*: "
        f"{step.step_description}",
    ]
    relation_specs = (
        (
            step.actor_ids,
            actor_names,
            "markdown_participants",
        ),
        (
            step.input_business_object_ids,
            business_object_names,
            "markdown_input_data",
        ),
        (
            step.output_business_object_ids,
            business_object_names,
            "markdown_output_data",
        ),
    )
    for identifiers, names_by_id, label_key in relation_specs:
        names = [
            names_by_id[identifier]
            for identifier in identifiers
            if identifier in names_by_id
        ]
        if names:
            lines.append(
                f"  - *{tr(label_key)}*: {', '.join(names)}"
            )
    return lines


def _flow_lines(detail, tr) -> list[str]:
    lines = [f"### 5.2 {tr('markdown_flows')}"]
    if not detail.flows:
        lines.append(tr("markdown_no_flows"))
        return lines

    actor_names = {
        actor.actor_id: actor.actor_name
        for actor in detail.actors
    }
    business_object_names = {
        business_object.business_object_id:
        business_object.business_object_name
        for business_object in detail.business_objects
    }
    for flow in detail.flows:
        lines.append(
            f"#### {tr('markdown_flow')}: {flow.flow_name}"
        )
        lines.append(
            f"- *{tr('markdown_flow_description')}*: "
            f"{flow.flow_description}"
        )
        if flow.flow_steps:
            lines.append("")
            lines.append(f"##### {tr('markdown_steps')}:")
            for step in flow.flow_steps:
                lines.extend(
                    _flow_step_lines(
                        step,
                        tr,
                        actor_names,
                        business_object_names,
                    )
                )
        lines.append("")
    return lines


def build_how_markdown_lines(detail, tr) -> list[str]:
    lines = [f"## 5. {tr('markdown_how')}", ""]
    lines.extend(_business_object_lines(detail, tr))
    lines.extend(_flow_lines(detail, tr))
    return lines
