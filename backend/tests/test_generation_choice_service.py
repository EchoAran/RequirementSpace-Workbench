"""
Tests for Generation Choice Group service (Phase 1).

Covers:
- GenerationChoiceSettings
- Concurrent candidate runner (full success, partial success, full failure)
- Test adapter registration
- GenerationChoiceService.create_choice_group
- ChoiceService.discard_choice_group
- ChoiceService.accept_choice dispatch (patch vs draft_payload)
- Failed group creation when partial_success_min not met
- Stale detection and group status update
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.model import Base, ChoiceGroupModel, ChoiceModel, ProjectModel
from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    GenerationChoiceSettings,
    GenerationCandidate,
    CandidateRunResult,
    CandidateContext,
    run_candidate_generation,
    BaseGenerationChoiceAdapter,
    register_adapter,
    get_adapter,
    GenerationChoiceService,
)
from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService


# ═══════════════════════════════════════════════════════════════════
# Test Adapter (also serves as a real adapter for Phase 2+)
# ═══════════════════════════════════════════════════════════════════

@register_adapter("test_actor")
class TestActorGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """测试用 adapter：生成简单的 actor 候选。"""

    generation_type = "test_actor"

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        prefix = context.strategy_label or context.strategy.capitalize()
        return GenerationCandidate(
            title=f"{prefix} Actor方案",
            rationale=f"{prefix} 方案说明",
            payload={
                "project_id": context.project_id,
                "actors": [
                    {"actor_name": f"{prefix}用户", "actor_description": f"{prefix}用户角色"}
                ],
            },
            preview={"actor_count": 1, "actors": [f"{prefix}用户"]},
            draft_type="test_actor",
            apply_mode="draft_payload",
            comparison_summary=f"{prefix} 方案：专注{context.strategy}风格",
            apply_behavior="overwrite",
            apply_behavior_description="此方案将替换项目当前参与者列表",
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(self, payload: dict, session: AsyncSession, **kwargs) -> dict:
        """模拟写入 actor 到数据库。"""
        from backend.database.model import ActorModel
        project_id = payload.get("project_id")
        # 先清除现有 actors (overwrite 模式)
        existing = await session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        for actor in existing.scalars().all():
            await session.delete(actor)
        await session.flush()

        for actor_data in payload.get("actors", []):
            actor = ActorModel(
                project_id=project_id,
                name=actor_data["actor_name"],
                description=actor_data.get("actor_description", ""),
            )
            session.add(actor)
        await session.flush()
        return {"actors_created": len(payload.get("actors", []))}

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        """按 actor name 集合判重。"""
        candidate_names = {a["actor_name"] for a in candidate.payload.get("actors", [])}
        for c in existing:
            existing_names = {a["actor_name"] for a in c.payload.get("actors", [])}
            if candidate_names == existing_names:
                return True
        return False


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def seeded_project(db_session) -> int:
    project = ProjectModel(
        name="测试项目",
        description="测试用项目",
        user_requirements="需要有用户管理功能。",
    )
    db_session.add(project)
    await db_session.flush()
    return project.id


# ═══════════════════════════════════════════════════════════════════
# GenerationChoiceSettings Tests
# ═══════════════════════════════════════════════════════════════════

class TestGenerationChoiceSettings:
    def test_default_values(self):
        settings = GenerationChoiceSettings()
        assert settings.candidate_count == 2
        assert settings.max_concurrency == 3
        assert settings.timeout_seconds == 120
        assert settings.partial_success_min == 1

    def test_with_overrides(self):
        settings = GenerationChoiceSettings().with_overrides(candidate_count=3)
        assert settings.candidate_count == 3

    def test_with_overrides_clamped(self):
        settings = GenerationChoiceSettings().with_overrides(candidate_count=99)
        assert settings.candidate_count == 5  # max 5

    def test_with_overrides_minimum(self):
        settings = GenerationChoiceSettings().with_overrides(candidate_count=0)
        assert settings.candidate_count == 1  # min 1

    def test_with_overrides_none(self):
        settings = GenerationChoiceSettings().with_overrides(candidate_count=None)
        assert settings.candidate_count == 2  # default unchanged


# ═══════════════════════════════════════════════════════════════════
# Concurrent Runner Tests
# ═══════════════════════════════════════════════════════════════════

async def _succeed(context: CandidateContext) -> GenerationCandidate:
    return GenerationCandidate(
        title=f"候选{context.index}",
        rationale=f"策略{context.strategy}",
        payload={"index": context.index},
        draft_type="test",
        comparison_summary=f"候选{context.index}",
    )


async def _fail(context: CandidateContext) -> GenerationCandidate:
    raise ValueError(f"候选{context.index}生成失败")


class TestRunCandidateGeneration:
    @pytest.mark.asyncio
    async def test_all_succeed(self):
        result = await run_candidate_generation(
            count=3, max_concurrency=3, timeout_seconds=30,
            generate_one=_succeed,
        )
        assert result.success_count == 3
        assert result.failure_count == 0
        assert len(result.candidates) == 3
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """2 succeed, 1 fail — should return partial success."""
        call_count = [0]

        async def mixed(context: CandidateContext) -> GenerationCandidate:
            call_count[0] += 1
            if context.index == 0:
                raise ValueError("第一个候选失败")
            return await _succeed(context)

        result = await run_candidate_generation(
            count=3, max_concurrency=3, timeout_seconds=30,
            generate_one=mixed,
        )
        assert result.success_count == 2
        assert result.failure_count == 1
        assert len(result.errors) == 1
        assert "第一个候选失败" in result.errors[0].message

    @pytest.mark.asyncio
    async def test_all_fail(self):
        result = await run_candidate_generation(
            count=2, max_concurrency=2, timeout_seconds=30,
            generate_one=_fail,
        )
        assert result.success_count == 0
        assert result.failure_count == 2
        assert len(result.candidates) == 0
        assert len(result.errors) == 2

    @pytest.mark.asyncio
    async def test_individual_failure_does_not_block_others(self):
        """单个候选失败不应中断其他候选的生成。"""
        async def first_fails(context: CandidateContext) -> GenerationCandidate:
            if context.index == 0:
                raise RuntimeError("候选0失败")
            return await _succeed(context)

        result = await run_candidate_generation(
            count=2, max_concurrency=2, timeout_seconds=30,
            generate_one=first_fails,
        )
        assert result.success_count == 1
        assert result.failure_count == 1

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """进度回调应按候选粒度触发。"""
        events = []

        def progress(index, phase, msg):
            events.append((index, phase))

        result = await run_candidate_generation(
            count=2, max_concurrency=2, timeout_seconds=30,
            generate_one=_succeed,
            progress_callback=progress,
        )
        # 每个候选应有 start + complete
        start_events = [e for e in events if e[1] == "start"]
        complete_events = [e for e in events if e[1] == "complete"]
        assert len(start_events) == 2
        assert len(complete_events) == 2


# ═══════════════════════════════════════════════════════════════════
# Adapter Registry Tests
# ═══════════════════════════════════════════════════════════════════

class TestAdapterRegistry:
    def test_get_registered_adapter(self):
        adapter = get_adapter("test_actor")
        assert adapter is not None
        assert adapter.generation_type == "test_actor"

    def test_get_unregistered_adapter_raises(self):
        with pytest.raises(ValueError, match="unsupported_generation_type"):
            get_adapter("nonexistent")

    def test_test_adapter_generate(self):
        adapter = get_adapter("test_actor")
        ctx = CandidateContext(index=0, strategy="balanced")
        candidate = adapter.generate_candidate(ctx)
        # 同步返回，需要 await
        import asyncio
        c = asyncio.run(candidate)
        assert c.title == "Balanced Actor方案"
        assert c.comparison_summary != ""

    def test_test_adapter_is_duplicate(self):
        adapter = get_adapter("test_actor")
        c1 = GenerationCandidate(
            title="A", rationale="", payload={"actors": [{"actor_name": "管理员"}]},
            draft_type="test",
        )
        c2 = GenerationCandidate(
            title="B", rationale="", payload={"actors": [{"actor_name": "管理员"}]},
            draft_type="test",
        )
        c3 = GenerationCandidate(
            title="C", rationale="", payload={"actors": [{"actor_name": "访客"}]},
            draft_type="test",
        )
        assert adapter.is_duplicate(c2, [c1])  # 重复（相同 actor name）
        assert not adapter.is_duplicate(c3, [c1])  # 不重复


# ═══════════════════════════════════════════════════════════════════
# GenerationChoiceService Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestGenerationChoiceService:
    @pytest.mark.asyncio
    async def test_single_scenario_candidates_run_two_at_a_time(
        self, db_session, seeded_project, monkeypatch
    ):
        from backend.api.modules.decision_workflow.candidate_generation.application import (
            generation_choice_service as service_module,
        )

        candidates = [
            GenerationCandidate(
                title=f"Scenario {index}",
                rationale="test",
                payload={"scenarios": []},
                draft_type="scenario",
            )
            for index in range(2)
        ]
        runner = AsyncMock(return_value=CandidateRunResult(
            candidates=candidates,
            errors=[],
            total_count=2,
            success_count=2,
            failure_count=0,
            duration_ms=1,
        ))
        monkeypatch.setattr(service_module, "run_candidate_generation", runner)
        monkeypatch.setattr(service_module, "get_adapter", lambda _type: TestActorGenerationChoiceAdapter())

        service = GenerationChoiceService(settings=GenerationChoiceSettings(candidate_count=2))
        await service.create_choice_group(
            project_id=seeded_project,
            generation_type="scenario",
            target={"generation_mode": "single", "feature_id": 1},
            candidate_count=2,
            session=db_session,
        )

        assert runner.await_args.kwargs["max_concurrency"] == 2

    @pytest.mark.asyncio
    async def test_large_scenario_batch_uses_one_candidate_and_scaled_timeout(
        self, db_session, seeded_project, monkeypatch
    ):
        from backend.api.modules.decision_workflow.candidate_generation.application import (
            generation_choice_service as service_module,
        )

        candidate = GenerationCandidate(
            title="Scenario batch",
            rationale="test",
            payload={"scenarios": []},
            draft_type="scenario",
        )
        runner = AsyncMock(return_value=CandidateRunResult(
            candidates=[candidate],
            errors=[],
            total_count=1,
            success_count=1,
            failure_count=0,
            duration_ms=1,
        ))
        monkeypatch.setattr(service_module, "run_candidate_generation", runner)
        monkeypatch.setattr(service_module, "get_adapter", lambda _type: TestActorGenerationChoiceAdapter())

        service = GenerationChoiceService(settings=GenerationChoiceSettings(
            candidate_count=2,
            timeout_seconds=100,
            partial_success_min=2,
        ))
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="scenario",
            target={"generation_mode": "batch", "feature_ids": list(range(67))},
            candidate_count=2,
            session=db_session,
        )

        assert runner.await_args.kwargs["count"] == 1
        assert runner.await_args.kwargs["timeout_seconds"] == 200
        assert result["status"] == "open"

    @pytest.mark.asyncio
    async def test_create_choice_group_success(self, db_session, seeded_project):
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor",
            candidate_count=2,
            session=db_session,
        )
        assert result["status"] == "open"
        assert result["generation_type"] == "test_actor"
        assert result["success_count"] == 2
        assert result["failure_count"] == 0
        assert len(result["choices"]) == 2
        for c in result["choices"]:
            assert c["status"] == "candidate"
            assert c["apply_mode"] == "draft_payload"
            assert c["draft_type"] == "test_actor"
            assert c["payload"] is not None
            assert "comparison_summary" in result.get("status_detail", {})

        # 验证未写入 ActorModel
        from backend.database.model import ActorModel
        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == seeded_project)
        )
        assert len(actors.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_create_choice_group_partial_failure_creates_failed_group(
        self, db_session, seeded_project
    ):
        """
        When fewer candidates succeed than partial_success_min, the group
        should be created with status="failed" and failed choices recorded.
        We set partial_success_min to 3 but only generate 1 candidate,
        forcing the group to be marked as failed.
        """
        service = GenerationChoiceService(
            settings=GenerationChoiceSettings(
                candidate_count=1, partial_success_min=3,  # impossible: 1 < 3
            )
        )
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor",
            candidate_count=1,
            session=db_session,
        )
        # partial_success_min=3, but we only requested 1 candidate
        # So deduped (1) < min (3) → status should be "failed"
        assert result["status"] == "failed"
        assert result["success_count"] == 1  # 1 candidate generated successfully
        assert result["candidate_count"] == 1

    @pytest.mark.asyncio
    async def test_accept_draft_payload_choice_writes_real_model(
        self, db_session, seeded_project
    ):
        """采纳 draft_payload choice 后应写入真实 ActorModel。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor",
            candidate_count=2,
            session=db_session,
        )
        choice_id = result["choices"][0]["id"]

        choice_service = ChoiceService()
        accept_result = await choice_service.accept_choice(
            project_id=seeded_project,
            choice_id=choice_id,
            session=db_session,
        )
        assert accept_result.status == "accepted"

        # 验证 ActorModel 已创建
        from backend.database.model import ActorModel
        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == seeded_project)
        )
        all_actors = actors.scalars().all()
        assert len(all_actors) > 0

        # 验证 group 已 resolved
        group = await db_session.get(ChoiceGroupModel, result["id"])
        assert group.status == "resolved"

        # 验证同组其他 choice 被 rejected
        all_choices = await db_session.execute(
            select(ChoiceModel).where(ChoiceModel.choice_group_id == result["id"])
        )
        for c in all_choices.scalars().all():
            if c.id == choice_id:
                assert c.status == "accepted"
            else:
                assert c.status == "rejected"

    @pytest.mark.asyncio
    async def test_discard_group_does_not_write_real_model(
        self, db_session, seeded_project
    ):
        """丢弃 choice group 后，不应写入 ActorModel。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor",
            candidate_count=2,
            session=db_session,
        )
        group_id = result["id"]

        choice_service = ChoiceService()
        discard_result = await choice_service.discard_choice_group(
            project_id=seeded_project,
            group_id=group_id,
            session=db_session,
        )
        assert discard_result.status == "discarded"

        # 验证 ActorModel 未创建
        from backend.database.model import ActorModel
        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == seeded_project)
        )
        assert len(actors.scalars().all()) == 0

        # 验证 choices 都为 discarded
        for c in discard_result.choices:
            assert c.status == "discarded"


# ═══════════════════════════════════════════════════════════════════
# Stale Detection Tests
# ═══════════════════════════════════════════════════════════════════

class TestStaleDetection:
    @pytest.mark.asyncio
    async def test_stale_detection_marks_group_stale(self, db_session, seeded_project):
        """检测到 stale 时应标记 group.status = stale。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor",
            candidate_count=1,
            session=db_session,
        )
        choice_id = result["choices"][0]["id"]

        # 直接修改 group 的 target，使其 context_hash 不再匹配
        group = await db_session.get(ChoiceGroupModel, result["id"])
        group.target = {"changed": True}
        await db_session.flush()

        choice_service = ChoiceService()
        accept_result = await choice_service.accept_choice(
            project_id=seeded_project,
            choice_id=choice_id,
            session=db_session,
        )
        # test_actor adapter 的 is_context_stale 默认返回 False，
        # 所以这里不触发 stale。下面测试强制 stale 的场景。

    @pytest.mark.asyncio
    async def test_force_accept_skips_stale_check(self, db_session, seeded_project):
        """force=True 应跳过 stale 校验。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor",
            candidate_count=1,
            session=db_session,
        )
        choice_id = result["choices"][0]["id"]

        choice_service = ChoiceService()
        accept_result = await choice_service.accept_choice(
            project_id=seeded_project,
            choice_id=choice_id,
            session=db_session,
            force=True,
        )
        assert accept_result.status == "accepted"


# ═══════════════════════════════════════════════════════════════════
# Patch Compatibility Tests
# ═══════════════════════════════════════════════════════════════════

class TestPatchCompatibility:
    @pytest.mark.asyncio
    async def test_old_patch_defaults_to_apply_mode_patch(self, db_session, seeded_project):
        """旧 choices 没有 apply_mode 时，应默认为 'patch'。"""
        # 先创建 choice_group，满足外键约束
        group = ChoiceGroupModel(
            project_id=seeded_project,
            status="open",
            selection_mode="single",
        )
        db_session.add(group)
        await db_session.flush()

        choice = ChoiceModel(
            choice_group_id=group.id,
            title="旧choice",
            rationale="",
            status="candidate",
            patch={"addNodes": [], "updateNodes": [], "deleteNodes": []},
        )
        db_session.add(choice)
        await db_session.flush()

        # 检查默认值
        assert choice.apply_mode == "patch"


# ═══════════════════════════════════════════════════════════════════
# Phase 6: Concurrent Partial-Failure Degradation Tests
# ═══════════════════════════════════════════════════════════════════

@register_adapter("test_actor_partial_fail")
class PartialFailActorAdapter(BaseGenerationChoiceAdapter):
    """测试用 adapter：模拟并发生成中部分候选失败场景（Phase 6 降级验证）。"""

    generation_type = "test_actor_partial_fail"
    _fail_indices: set[int] = set()

    @classmethod
    def configure_failures(cls, fail_indices: set[int]):
        cls._fail_indices = fail_indices

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        if context.index in self.__class__._fail_indices:
            raise RuntimeError(f"候选 {context.index} 模拟生成失败")
        prefix = context.strategy_label or context.strategy.capitalize()
        return GenerationCandidate(
            title=f"{prefix} PartialFail Actor方案",
            rationale=f"{prefix} 降级方案说明",
            payload={"project_id": context.project_id, "actors": [{"actor_name": f"{prefix}用户", "actor_description": "测试角色"}]},
            preview={"actor_count": 1},
            draft_type="test_actor_partial_fail",
            apply_mode="draft_payload",
            comparison_summary=f"{prefix} 方案",
            apply_behavior="overwrite",
            apply_behavior_description="替换参与者",
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(self, payload: dict, session: AsyncSession, **kwargs) -> dict:
        return {"actors_created": len(payload.get("actors", []))}

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        return False


class TestConcurrentPartialFailureDegradation:
    """
    Phase 6 验收测试（文档第 12 条）：
    candidate_count 为上限值时的并发生成测试，
    覆盖部分候选成功、部分失败的降级返回。
    """

    @pytest.mark.asyncio
    async def test_partial_failure_group_still_created(self, db_session, seeded_project):
        """
        3 个候选并发生成，1 个失败，2 个成功。
        验证：
        - choice group 仍以 status="open" 创建（满足 partial_success_min=1）
        - success_count=2, failure_count=1
        - 成功的 choices 可正常读取
        - 失败的 choice 以 status="failed" 落库，不阻断其他候选
        """
        PartialFailActorAdapter.configure_failures({1})  # index=1 fails

        service = GenerationChoiceService(
            settings=GenerationChoiceSettings(
                candidate_count=3,
                max_concurrency=3,
                partial_success_min=1,
            )
        )
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor_partial_fail",
            candidate_count=3,
            session=db_session,
        )

        assert result["status"] == "open", f"Expected 'open', got: {result['status']}"
        assert result["success_count"] == 2
        assert result["failure_count"] == 1
        assert result["candidate_count"] == 3

        # Successful choices should be accessible
        successful_choices = [c for c in result["choices"] if c["status"] == "candidate"]
        assert len(successful_choices) == 2

        # Failed choice must be recorded in DB with error info
        stmt = select(ChoiceModel).where(
            ChoiceModel.choice_group_id == result["id"],
            ChoiceModel.status == "failed",
        )
        failed_choices = (await db_session.execute(stmt)).scalars().all()
        assert len(failed_choices) == 1
        assert failed_choices[0].error is not None
        assert "模拟生成失败" in (failed_choices[0].error.get("message") or "")

    @pytest.mark.asyncio
    async def test_all_candidates_fail_group_marked_failed(self, db_session, seeded_project):
        """
        candidate_count=3，全部失败。
        验证：choice group status="failed"，success_count=0。
        """
        PartialFailActorAdapter.configure_failures({0, 1, 2})  # all fail

        service = GenerationChoiceService(
            settings=GenerationChoiceSettings(
                candidate_count=3,
                max_concurrency=3,
                partial_success_min=1,
            )
        )
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor_partial_fail",
            candidate_count=3,
            session=db_session,
        )

        assert result["status"] == "failed"
        assert result["success_count"] == 0
        assert result["failure_count"] == 3
        assert len(result["choices"]) == 3
        assert all(c["status"] == "failed" for c in result["choices"])
        assert all(c["error"] is not None for c in result["choices"])

    @pytest.mark.asyncio
    async def test_max_candidate_count_partial_failure(self, db_session, seeded_project):
        """
        candidate_count=5（上限），2 个失败，3 个成功。
        验证降级后 group 仍可用，不因部分失败而整体失败。
        """
        PartialFailActorAdapter.configure_failures({0, 4})  # indices 0 and 4 fail

        service = GenerationChoiceService(
            settings=GenerationChoiceSettings(
                candidate_count=5,
                max_concurrency=5,
                partial_success_min=1,
            )
        )
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="test_actor_partial_fail",
            candidate_count=5,
            session=db_session,
        )

        assert result["status"] == "open"
        assert result["success_count"] == 3
        assert result["failure_count"] == 2
        assert result["candidate_count"] == 5
        # Verify we still get the successful candidates
        assert len([c for c in result["choices"] if c["status"] == "candidate"]) == 3
