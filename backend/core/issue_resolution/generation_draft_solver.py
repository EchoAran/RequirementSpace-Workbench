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

        choice_group_resolution = await self._try_create_choice_group_resolution(
            project_id,
            issue_code,
            target,
            metadata,
            session,
        )
        if choice_group_resolution is not None:
            return choice_group_resolution

        payload = self._build_draft_payload(
            project_id,
            issue_code,
            target,
            metadata,
        )
        return self._build_draft_resolution(issue_code, config, payload)

    async def _try_create_choice_group_resolution(
        self,
        project_id: int,
        issue_code: str,
        target: IssueTarget | None,
        metadata: dict,
        session,
    ) -> IssueResolution | None:
        generation_types = {
            "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA": "acceptance_criteria",
            "LEAF_FEATURE_WITHOUT_SCOPE": "scope",
        }
        generation_type = generation_types.get(issue_code)
        if generation_type is None:
            return None

        from backend.core.issue_resolution.ports import (
            get_choice_group_creator,
            get_choice_group_settings,
        )

        creator = get_choice_group_creator()
        settings = get_choice_group_settings()
        if creator is None or settings is None:
            return None

        generation_target = self._build_generation_target(issue_code, target)
        try:
            if not settings.is_generation_type_enabled(generation_type):
                return None
            choice_group = await creator.create_choice_group(
                project_id=project_id,
                generation_type=generation_type,
                target=generation_target,
                session=session,
                issue_code=issue_code,
                issue_id=metadata.get("issue_id"),
                stage=metadata.get("stage"),
                source_type="issue_repair",
                source_id=metadata.get("issue_fingerprint"),
                context_hash=metadata.get("context_hash"),
            )
            return self._build_choice_group_resolution(issue_code, choice_group)
        except Exception:
            # Preserve the existing compatibility fallback to draft generation.
            return None

    @staticmethod
    def _build_generation_target(
        issue_code: str,
        target: IssueTarget | None,
    ) -> dict:
        if target is None or target.targetId is None:
            return {}
        try:
            target_id = int(target.targetId)
        except (ValueError, TypeError):
            return {}
        if issue_code == "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA":
            return {"scenario_id": target_id}
        if issue_code == "LEAF_FEATURE_WITHOUT_SCOPE":
            return {"feature_id": target_id}
        return {}

    @staticmethod
    def _build_choice_group_resolution(
        issue_code: str,
        choice_group: dict,
    ) -> IssueResolution:
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

    @staticmethod
    def _build_draft_payload(
        project_id: int,
        issue_code: str,
        target: IssueTarget | None,
        metadata: dict,
    ) -> dict:
        payload = {"project_id": project_id, **metadata}
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
                    payload.setdefault("feature_id", target_id)
        return payload

    @staticmethod
    def _build_draft_resolution(
        issue_code: str,
        config: dict,
        payload: dict,
    ) -> IssueResolution:
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
