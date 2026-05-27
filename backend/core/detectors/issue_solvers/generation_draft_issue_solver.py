from backend.core.detectors.issue_solvers.base_issue_solver import (
    BaseIssueSolver,
)
from backend.schemas import IssueResolution, IssueTarget


class GenerationDraftIssueSolver(BaseIssueSolver):
    _draft_map = {
        "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO": {
            "title": "生成场景草稿",
            "description": "为该功能与参与者组合创建场景草稿。",
            "draft_type": "scenario_generation",
            "endpoint": "/api/scenario_generation_drafts/{draft_id}/confirm",
            "payload_keys": ("feature_id", "actor_id"),
        },
        "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA": {
            "title": "生成成功标准草稿",
            "description": "为该场景创建成功标准草稿。",
            "draft_type": "acceptance_criteria_generation",
            "endpoint": (
                "/api/acceptance_criteria_generation_drafts/"
                "{draft_id}/confirm"
            ),
            "payload_keys": ("scenario_id",),
        },
        "LEAF_FEATURE_WITHOUT_SCOPE": {
            "title": "生成范围草稿",
            "description": "为当前项目创建功能范围草稿。",
            "draft_type": "scope_generation",
            "endpoint": "/api/scope_generation_drafts/{draft_id}/confirm",
            "payload_keys": ("feature_id",),
        },
    }

    async def resolve(
        self,
        project_id: int,
        issue_code: str,
        target: IssueTarget | None,
        metadata: dict,
        session,
    ) -> IssueResolution:
        config = self._draft_map.get(issue_code)

        if config is None:
            raise ValueError("unsupported_issue_code")

        payload = {
            "project_id": project_id,
            **metadata,
        }

        if target is not None and target.targetId is not None:
            target_id = target.targetId

            if issue_code == "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA":
                payload.setdefault("scenario_id", target_id)

            if issue_code == "LEAF_FEATURE_WITHOUT_SCOPE":
                payload.setdefault("feature_id", target_id)

            if issue_code == "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO":
                if isinstance(target_id, str) and ":" in target_id:
                    try:
                        feat_str, actor_str = target_id.split(":", 1)
                        payload.setdefault("feature_id", int(feat_str))
                        payload.setdefault("actor_id", int(actor_str))
                    except (ValueError, TypeError):
                        pass
                elif isinstance(target_id, int):
                    # Fallback if target_id is just feature_id
                    payload.setdefault("feature_id", target_id)

        return IssueResolution(
            issueCode=issue_code,
            resolutionType="generation_draft",
            title=config["title"],
            description=config["description"],
            action={
                "kind": "create_draft",
                "draft_type": config["draft_type"],
                "endpoint": config["endpoint"],
                "payload": payload,
            },
        )
