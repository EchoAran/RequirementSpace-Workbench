from backend.api.modules.ai_interaction.ai_explain.application.context_locale import (
    localize_ai_explain_context,
)


def test_ai_explain_structural_context_labels_follow_english_locale():
    source = "=== 项目总览：Inventory ===\n参与者：2个\n描述：（无描述）\n关联流程"
    result = localize_ai_explain_context(source, "en-US")

    assert "Project overview" in result
    assert "Actors" in result
    assert "Description: (no description)" in result
    assert "Related flows" in result
    assert not any(label in result for label in ("项目总览", "参与者", "描述", "关联流程"))
