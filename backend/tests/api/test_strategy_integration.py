import pytest
from unittest.mock import patch
import backend.tests.test_generation_choice_adapters  # noqa: F401
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    GenerationCandidate,
    GenerationChoiceService,
)
from backend.api.modules.project_configuration.application.generation_strategy_config_service import (
    GenerationStrategyConfigService,
)
from backend.api.modules.project_configuration.schemas import (
    GenerationStrategyConfigUpdate,
    GenerationStrategyItemSchema,
)
from backend.api.modules.requirements_core.actor.application.choice_adapter import (
    ActorGenerationChoiceAdapter,
)
from backend.database.model import (
    Base,
    BranchWorkspaceModel,
    RequirementBranchModel,
    ChoiceGroupModel,
    ChoiceModel,
    ProjectModel,
    UserModel,
)

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


async def _mock_gen(self, context):
    return GenerationCandidate(
        title=f"{context.strategy_label} 方案",
        rationale=f"{context.strategy_label} 摘要",
        comparison_summary=f"角色划分：{context.strategy_label}",
        payload={"project_id": context.project_id, "workspace_id": context.workspace_id, "actors": [{"actor_name": f"Actor_{context.strategy_id}", "actor_description": "desc"}]},
        apply_behavior="overwrite",
        apply_behavior_description="desc",
        strategy_id=context.strategy_id,
        strategy_label=context.strategy_label,
    )


@pytest.fixture
async def test_db():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield session_factory
    await engine.dispose()

@pytest.mark.asyncio
async def test_strategy_integration_workflow(test_db):
    async with test_db() as session:
        # 1. Create a dummy project
        owner = UserModel(email="strategy_owner@test.com", password_hash="test-hash")
        session.add(owner)
        await session.flush()

        project = ProjectModel(
            name="Strategy Integration Test Project",
            owner_user_id=owner.id,
            user_requirements="Test requirements spec."
        )
        session.add(project)
        await session.flush()
        branch = RequirementBranchModel(project_id=project.id, name="codex/strategy", created_by_user_id=owner.id)
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id)
        session.add(workspace)
        await session.flush()
        workspace_id = workspace.id
        await session.commit()
        project_id = project.id
        owner_id = owner.id

    # 2. Save a custom generation strategy configuration for the project
    # We configure 3 candidates, and define 3 enabled strategies applicable to "actor"
    # and 1 enabled strategy not applicable to "actor" (e.g. only for "scenario")
    # and 1 disabled strategy.
    strategy_service = GenerationStrategyConfigService()
    custom_config = GenerationStrategyConfigUpdate(
        enabled=True,
        candidate_count=3,
        strategies=[
            GenerationStrategyItemSchema(
                id="strat_1",
                label="自定义策略A",
                description="Desc A",
                instruction="This is instruction for custom strategy A, minimum 20 chars.",
                generation_types=["actor"],
                enabled=True,
                order=0
            ),
            GenerationStrategyItemSchema(
                id="strat_2",
                label="自定义策略B",
                description="Desc B",
                instruction="This is instruction for custom strategy B, minimum 20 chars.",
                generation_types=["actor"],
                enabled=True,
                order=1
            ),
            GenerationStrategyItemSchema(
                id="strat_3",
                label="自定义策略C",
                description="Desc C",
                instruction="This is instruction for custom strategy C, minimum 20 chars.",
                generation_types=["actor"],
                enabled=True,
                order=2
            ),
            GenerationStrategyItemSchema(
                id="strat_only_scenario",
                label="仅场景策略",
                description="Desc Scenario Only",
                instruction="This is instruction for scenario only strategy, minimum 20 chars.",
                generation_types=["scenario"],
                enabled=True,
                order=3
            ),
            GenerationStrategyItemSchema(
                id="strat_disabled",
                label="已禁用策略",
                description="Desc Disabled",
                instruction="This is instruction for disabled strategy, minimum 20 chars.",
                generation_types=["actor"],
                enabled=False,
                order=4
            )
        ]
    )

    async with test_db() as session:
        await strategy_service.save_for_project(
            project_id=project_id,
            user_id=owner_id,
            req=custom_config,
            session=session
        )
        await session.commit()

    # 3. Trigger candidate generation (create_choice_group) for "actor"
    choice_service = GenerationChoiceService()

    with patch.object(ActorGenerationChoiceAdapter, "generate_candidate", _mock_gen):
        async with test_db() as session:
            res = await choice_service.create_choice_group(
                project_id=project_id,
                generation_type="actor",
                workspace_id=workspace_id,
                target={"project_id": project_id},
                session=session
            )
            await session.commit()
            group_id = res["id"]

    # 4. Assertions on generated choice group and choices
    async with test_db() as session:
        stmt = select(ChoiceGroupModel).where(ChoiceGroupModel.id == group_id)
        group_db = (await session.execute(stmt)).scalar_one()
        print("\n\nDEBUG STATUS DETAIL:", group_db.status_detail, "\n\n")
        assert group_db.candidate_count == 3
        assert group_db.success_count == 3
        assert group_db.failure_count == 0

        # Verify choices
        stmt_choices = select(ChoiceModel).where(ChoiceModel.choice_group_id == group_id).order_by(ChoiceModel.id)
        choices_db = (await session.execute(stmt_choices)).scalars().all()
        assert len(choices_db) == 3

        # Assert strategy_id and strategy_label snapshots are stored
        assert choices_db[0].strategy_id == "strat_1"
        assert choices_db[0].strategy_label == "自定义策略A"
        assert choices_db[1].strategy_id == "strat_2"
        assert choices_db[1].strategy_label == "自定义策略B"
        assert choices_db[2].strategy_id == "strat_3"
        assert choices_db[2].strategy_label == "自定义策略C"

        # Check choice titles used correct labels
        assert "自定义策略A" in choices_db[0].title
        assert "自定义策略B" in choices_db[1].title
        assert "自定义策略C" in choices_db[2].title

        # Check comparison summary uses correct labels
        assert "自定义策略A" in group_db.status_detail["comparison_summary"]

        first_choice_id = choices_db[0].id

        # 5. Test single choice regeneration (regenerate_choice)
        # Regenerate first choice (strategy_id="strat_1") and ensure it retains its strategy settings
        original_ids = {c.id for c in choices_db}
        with patch.object(ActorGenerationChoiceAdapter, "generate_candidate", _mock_gen):
            async with test_db() as session:
                new_choice_res = await choice_service.regenerate_choice(
                    project_id=project_id,
                    choice_id=first_choice_id,
                    user_feedback="Make it better",
                    session=session
                )
                await session.commit()

                choices_list = new_choice_res.get("choices", [])
                new_choice_data = next((c for c in choices_list if c["id"] not in original_ids), None)
                assert new_choice_data is not None
                new_choice_id = new_choice_data["id"]

    async with test_db() as session:
        stmt_new = select(ChoiceModel).where(ChoiceModel.id == new_choice_id)
        new_choice_db = (await session.execute(stmt_new)).scalar_one()
        assert new_choice_db.strategy_id == "strat_1"
        assert new_choice_db.strategy_label == "自定义策略A"
        assert "自定义策略A" in new_choice_db.title


@pytest.mark.asyncio
async def test_strategy_feature_flag_falls_back_to_defaults(test_db, monkeypatch):
    monkeypatch.setenv("PROJECT_GENERATION_STRATEGIES_ENABLED", "false")

    async with test_db() as session:
        owner = UserModel(email="strategy_flag_owner@test.com", password_hash="test-hash")
        session.add(owner)
        await session.flush()

        project = ProjectModel(
            name="Strategy Flag Test Project",
            owner_user_id=owner.id,
            user_requirements="Test requirements spec."
        )
        session.add(project)
        await session.flush()
        branch = RequirementBranchModel(project_id=project.id, name="codex/strategy", created_by_user_id=owner.id)
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id)
        session.add(workspace)
        await session.flush()
        workspace_id = workspace.id
        await session.flush()
        project_id = project.id
        owner_id = owner.id

        strategy_service = GenerationStrategyConfigService()
        await strategy_service.save_for_project(
            project_id=project_id,
            user_id=owner_id,
            req=GenerationStrategyConfigUpdate(
                enabled=True,
                candidate_count=1,
                strategies=[
                    GenerationStrategyItemSchema(
                        id="custom_flag_strategy",
                        label="自定义开关策略",
                        description="Desc",
                        instruction="This custom instruction should be ignored when flag is disabled.",
                        generation_types=["actor"],
                        enabled=True,
                        order=0
                    )
                ]
            ),
            session=session
        )
        await session.commit()

    with patch.object(ActorGenerationChoiceAdapter, "generate_candidate", _mock_gen):
        async with test_db() as session:
            res = await GenerationChoiceService().create_choice_group(
                project_id=project_id,
                generation_type="actor",
                workspace_id=workspace_id,
                target={"project_id": project_id},
                session=session
            )
            await session.commit()
            group_id = res["id"]

    async with test_db() as session:
        choices_db = (await session.execute(
            select(ChoiceModel).where(ChoiceModel.choice_group_id == group_id).order_by(ChoiceModel.id)
        )).scalars().all()

        assert len(choices_db) == 2
        assert [c.strategy_id for c in choices_db] == ["balanced", "comprehensive"]
        assert all(c.strategy_label != "自定义开关策略" for c in choices_db)
