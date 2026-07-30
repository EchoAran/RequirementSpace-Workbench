from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.preview_convergence.application.shadow_convergence import (
    PreviewShadowConvergenceService,
)
from backend.api.modules.preview_convergence.application.shadow_project_creator import (
    build_project_snapshot,
    calculate_stable_snapshot_hash,
)
from backend.database.model import (
    ActorModel,
    Base,
    FeatureModel,
    FeatureRelationModel,
    PreviewShadowDraftModel,
    ProjectModel,
    PrototypePreviewModel,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _add_project(session: AsyncSession) -> ProjectModel:
    project = ProjectModel(
        name="提交特征测试",
        description="锁定影子草稿提交行为",
        user_requirements="建立父子功能并生成原型",
        kano_status="pending",
    )
    session.add(project)
    await session.flush()
    return project


def _empty_patch() -> dict[str, list]:
    return {
        "actors_added": [],
        "features_added": [],
        "feature_actor_links_added": [],
        "scenarios_added": [],
        "acceptance_criteria_added": [],
        "business_objects_added": [],
        "business_object_attributes_added": [],
        "flows_added": [],
        "flow_steps_added": [],
        "scopes_added": [],
    }


@pytest.mark.asyncio
async def test_commit_guard_errors_keep_their_current_precedence(db_session):
    project = await _add_project(db_session)
    service = PreviewShadowConvergenceService()

    with pytest.raises(ValueError, match="^shadow_draft_not_found$"):
        await service.commit_shadow_draft(project.id, "missing", db_session)

    snapshot = await build_project_snapshot(project.id, db_session)
    draft = PreviewShadowDraftModel(
        project_id=project.id,
        draft_id="guard-draft",
        status="generating",
        source="shadow_project",
        base_snapshot_hash=calculate_stable_snapshot_hash(snapshot),
        base_snapshot_json=snapshot,
        patch_json=_empty_patch(),
        shadow_snapshot_json=snapshot,
    )
    db_session.add(draft)
    await db_session.flush()

    with pytest.raises(ValueError, match="^shadow_draft_not_ready$"):
        await service.commit_shadow_draft(project.id, draft.draft_id, db_session)

    draft.status = "ready"
    draft.base_snapshot_hash = "stale-hash"
    await db_session.flush()
    with pytest.raises(ValueError, match="^shadow_draft_conflict$"):
        await service.commit_shadow_draft(project.id, draft.draft_id, db_session)


@pytest.mark.asyncio
async def test_commit_preserves_topological_order_and_prototype_id_mapping(db_session):
    project = await _add_project(db_session)
    snapshot = await build_project_snapshot(project.id, db_session)
    patch_json = _empty_patch()
    patch_json["actors_added"] = [
        {
            "temp_id": "tmp_actor_1",
            "name": "管理员",
            "description": "维护系统配置",
        }
    ]
    patch_json["features_added"] = [
        {
            "temp_id": "tmp_child_a",
            "parent_ref": "tmp_parent",
            "name": "子功能 A",
            "description": "第一个输入但最后插入",
        },
        {
            "temp_id": "tmp_parent",
            "parent_ref": None,
            "name": "父功能",
            "description": "父级",
        },
        {
            "temp_id": "tmp_child_b",
            "parent_ref": "tmp_parent",
            "name": "子功能 B",
            "description": "父节点解析后立即插入",
        },
        {
            "temp_id": "tmp_child_c",
            "parent_ref": "tmp_parent",
            "name": "子功能 C",
            "description": "父节点解析后立即插入",
        },
    ]
    for child_ref in ("tmp_child_a", "tmp_child_b", "tmp_child_c"):
        patch_json["scopes_added"].append(
            {
                "feature_ref": child_ref,
                "status": "CURRENT",
                "reason": "特征测试",
            }
        )

    draft = PreviewShadowDraftModel(
        project_id=project.id,
        draft_id="topological-draft",
        status="ready",
        source="shadow_project",
        base_snapshot_hash=calculate_stable_snapshot_hash(snapshot),
        base_snapshot_json=snapshot,
        patch_json=patch_json,
        shadow_snapshot_json=snapshot,
        prototype_preview_json={
            "html": "fallback",
            "pages": [
                {
                    "roleId": -1001,
                    "roleName": "管理员",
                    "featureId": -1002,
                    "featureName": "子功能 A",
                    "html": "<main>A</main>",
                    "javascript": "window.a = true",
                    "css": "main { color: red; }",
                }
            ],
        },
    )
    db_session.add(draft)
    await db_session.flush()

    project_detail = SimpleNamespace(
        model_dump=lambda **_: {"projectId": project.id, "name": project.name}
    )
    prototype_service = MagicMock()
    prototype_service.generate_preview = AsyncMock()
    prototype_service._project_service.get_project_detail = AsyncMock(
        return_value=project_detail
    )
    service = PreviewShadowConvergenceService()

    with patch(
        "backend.api.modules.preview_convergence.ports.get_prototype_generation_service",
        return_value=prototype_service,
    ):
        await service.commit_shadow_draft(project.id, draft.draft_id, db_session)

    features = (
        await db_session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project.id)
        )
    ).scalars().all()
    feature_by_name = {feature.name: feature for feature in features}
    actor = (
        await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == project.id)
        )
    ).scalar_one()
    relations = (
        await db_session.execute(
            select(FeatureRelationModel).order_by(FeatureRelationModel.position)
        )
    ).scalars().all()
    assert [
        (relation.child_feature_id, relation.position)
        for relation in relations
    ] == [
        (feature_by_name["子功能 B"].id, 0),
        (feature_by_name["子功能 C"].id, 1),
        (feature_by_name["子功能 A"].id, 2),
    ]

    preview = (
        await db_session.execute(
            select(PrototypePreviewModel).where(
                PrototypePreviewModel.project_id == project.id
            )
        )
    ).scalar_one()
    assert preview.pages == [
        {
            "page_id": (
                f"role-{actor.id}"
                f"-feature-{feature_by_name['子功能 A'].id}"
            ),
            "role_id": actor.id,
            "role_name": "管理员",
            "feature_id": feature_by_name["子功能 A"].id,
            "feature_name": "子功能 A",
            "html": "<main>A</main>",
            "javascript": "window.a = true",
            "css": "main { color: red; }",
            "source": "committed_shadow_project",
            "status": "ready",
        }
    ]
    assert draft.status == "committed"
    assert project.kano_status == "generated"
    assert project.unlocked_stages == "what,how,scope"
    prototype_service.generate_preview.assert_awaited_once_with(
        project_id=project.id,
        force_regenerate=True,
    )
