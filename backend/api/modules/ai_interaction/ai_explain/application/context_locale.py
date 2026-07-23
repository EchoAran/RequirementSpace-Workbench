CONTEXT_LABELS_EN = {
    "（无描述）": "(no description)",
    "（每个功能的分类与理由）": "(classification and reason for each feature)",
    "关联参与者": "Related actors",
    "参与者": "Actors",
    "功能模块": "Feature module",
    "功能点": "Feature",
    "关联功能": "Related features",
    "子功能": "Child features",
    "所属父功能": "Parent feature",
    "关联场景": "Related scenarios",
    "场景": "Scenarios",
    "流程步骤": "Flow steps",
    "关联流程": "Related flows",
    "流程": "Flows",
    "业务数据对象": "Business objects",
    "属性": "Attributes",
    "Kano 分析与范围决策": "Kano analysis and scope decisions",
    "项目总览": "Project overview",
    "未知项目": "Unknown project",
    "项目": "Project",
    "状态": "Status",
    "理由": "Reason",
    "正面论证": "Positive rationale",
    "反面论证": "Negative rationale",
    "描述": "Description",
    "如需详细信息，请选择更具体的范围或在问题中指定对象名称。": (
        "Select a more specific scope or name an object in the question for details."
    ),
    "个": "",
    "：": ": ",
}


def localize_ai_explain_context(text: str, locale: str) -> str:
    if locale != "en-US":
        return text
    for source, target in sorted(
        CONTEXT_LABELS_EN.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        text = text.replace(source, target)
    return text
