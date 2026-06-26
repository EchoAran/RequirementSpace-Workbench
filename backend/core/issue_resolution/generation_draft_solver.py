from backend.core.issue_resolution.base_solver import (
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

        # P2 Upgrade: Attempt to generate choice group if enabled
        if issue_code in ("SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA", "LEAF_FEATURE_WITHOUT_SCOPE"):
            from backend.core.issue_resolution.ports import get_choice_group_creator, get_choice_group_settings
            creator = get_choice_group_creator()
            settings = get_choice_group_settings()
            if creator is not None and settings is not None:
                gen_type = {
                    "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA": "acceptance_criteria",
                    "LEAF_FEATURE_WITHOUT_SCOPE": "scope",
                }[issue_code]

                # Map target
                gen_target = {}
                if target is not None and target.targetId is not None:
                    try:
                        target_id = int(target.targetId)
                        if issue_code == "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA":
                            gen_target = {"scenario_id": target_id}
                        elif issue_code == "LEAF_FEATURE_WITHOUT_SCOPE":
                            gen_target = {"feature_id": target_id}
                    except (ValueError, TypeError):
                        pass

                try:
                    # check if choice group is enabled for this type
                    if settings.is_generation_type_enabled(gen_type):
                        issue_id = metadata.get("issue_id")
                        stage = metadata.get("stage")
                        issue_fp = metadata.get("issue_fingerprint")
                        context_hash = metadata.get("context_hash")

                        choice_group = await creator.create_choice_group(
                            project_id=project_id,
                            generation_type=gen_type,
                            target=gen_target,
                            session=session,
                            issue_code=issue_code,
                            issue_id=issue_id,
                            stage=stage,
                            source_type="issue_repair",
                            source_id=issue_fp,
                            context_hash=context_hash,
                        )
                        # Return choice_group resolution
                        return IssueResolution(
                            issueCode=issue_code,
                            resolutionType="choice_group",
                            title="选择处理方案",
                            description=f"AI 找到 {len(choice_group.get('choices', []))} 个可行方案，请选择。",
                            action={
                                "kind": "open_choice_group",
                                "choice_group_id": choice_group["id"],
                                "payload": {"choice_group": choice_group},
                            },
                        )
                except Exception as e:
                    # Log and fallback to old draft generation
                    pass

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

    def get_draft_type(self, issue_code: str) -> str | None:
        """Return the draft_type for a given issue code, or None."""
        config = self._draft_map.get(issue_code)
        return config["draft_type"] if config else None
