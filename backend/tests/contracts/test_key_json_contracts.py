from backend.api.modules.project_lifecycle.schemas.project import ProjectDetailResponse
from backend.api.modules.decision_workflow.choice_group.schemas import ChoiceResponse, ChoiceGroupResponse
from backend.api.modules.diagnosis_quality.next_suggestion.schemas import NextSuggestionResponse, NextSuggestionResponseItem
from backend.api.modules.diagnosis_quality.perception.schemas import PerceptionSlotFillingDraftResponse
from backend.api.modules.ai_interaction.ai_add.schemas import AIAddGenerateDraftResponse

def test_key_json_fields_are_snake_case():
    # 1. ProjectDetailResponse contract fields
    project_fields = ProjectDetailResponse.model_fields
    assert "project_id" in project_fields, "project_id must exist in ProjectDetailResponse"
    assert "projectId" not in project_fields
    
    # 2. ChoiceResponse contract fields
    choice_fields = ChoiceResponse.model_fields
    assert "choice_group_id" in choice_fields, "choice_group_id must exist in ChoiceResponse"
    assert "choiceGroupId" not in choice_fields

    # 3. ChoiceGroupResponse contract fields
    choice_group_fields = ChoiceGroupResponse.model_fields
    assert "project_id" in choice_group_fields, "project_id must exist in ChoiceGroupResponse"
    assert "projectId" not in choice_group_fields
    assert "source_type" in choice_group_fields, "source_type must exist in ChoiceGroupResponse"
    assert "sourceType" not in choice_group_fields
    assert "context_hash" in choice_group_fields, "context_hash must exist in ChoiceGroupResponse"
    assert "contextHash" not in choice_group_fields

    # 4. NextSuggestionResponse contract fields
    suggestion_fields = NextSuggestionResponse.model_fields
    assert "project_id" in suggestion_fields, "project_id must exist in NextSuggestionResponse"
    assert "projectId" not in suggestion_fields
    
    # 5. NextSuggestionResponseItem contract fields
    item_fields = NextSuggestionResponseItem.model_fields
    assert "source_type" in item_fields, "source_type must exist in NextSuggestionResponseItem"
    assert "sourceType" not in item_fields

    # 6. PerceptionSlotFillingDraftResponse contract fields
    perception_fields = PerceptionSlotFillingDraftResponse.model_fields
    assert "project_id" in perception_fields, "project_id must exist in PerceptionSlotFillingDraftResponse"
    assert "draft_id" in perception_fields, "draft_id must exist in PerceptionSlotFillingDraftResponse"
    assert "perception_job_id" in perception_fields, "perception_job_id must exist in PerceptionSlotFillingDraftResponse"
    assert "projectId" not in perception_fields
    assert "draftId" not in perception_fields
    assert "perceptionJobId" not in perception_fields

    # 7. AIAddGenerateDraftResponse contract fields
    ai_add_fields = AIAddGenerateDraftResponse.model_fields
    assert "draft_id" in ai_add_fields, "draft_id must exist in AIAddGenerateDraftResponse"
    assert "project_id" in ai_add_fields, "project_id must exist in AIAddGenerateDraftResponse"
    assert "target_type" in ai_add_fields, "target_type must exist in AIAddGenerateDraftResponse"
    assert "draftId" not in ai_add_fields
    assert "projectId" not in ai_add_fields
    assert "targetType" not in ai_add_fields
