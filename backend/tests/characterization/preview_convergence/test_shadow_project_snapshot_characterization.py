import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.preview_convergence.application.shadow_project_creator import (
    build_project_snapshot,
)
from backend.api.modules.version_control.application.clean_initialization import (
    create_initial_workspace,
)
from backend.database.model import (
    Base,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    ProjectModel,
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


@pytest.mark.asyncio
async def test_build_project_snapshot_preserves_object_and_attribute_order(
    db_session,
):
    project = ProjectModel(
        name="快照顺序",
        description="锁定批量属性加载语义",
        owner_user_id=1,
        user_requirements="保存业务对象",
    )
    db_session.add(project)
    await db_session.flush()
    _, workspace = await db_session.run_sync(lambda s: create_initial_workspace(s, project))
    first_object = BusinessObjectModel(
        project_id=project.id,
        workspace_id=workspace.id,
        name="订单",
        description="第一个对象",
    )
    second_object = BusinessObjectModel(
        project_id=project.id,
        workspace_id=workspace.id,
        name="客户",
        description="第二个对象",
    )
    db_session.add_all([first_object, second_object])
    await db_session.flush()
    db_session.add_all(
        [
            BusinessObjectAttributeModel(
                business_object_id=second_object.id,
                name="客户名称",
                description="先插入但属于第二个对象",
                data_type="string",
                example="张三",
            ),
            BusinessObjectAttributeModel(
                business_object_id=first_object.id,
                name="订单编号",
                description="第一个属性",
                data_type="string",
                example="SO-1",
            ),
            BusinessObjectAttributeModel(
                business_object_id=first_object.id,
                name="金额",
                description="第二个属性",
                data_type="decimal",
                example="100",
            ),
            BusinessObjectAttributeModel(
                business_object_id=second_object.id,
                name="客户编号",
                description="后插入",
                data_type="string",
                example="C-1",
            ),
        ]
    )
    await db_session.flush()

    attribute_select_count = 0

    def count_attribute_selects(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        nonlocal attribute_select_count
        normalized_statement = statement.lower()
        if (
            normalized_statement.lstrip().startswith("select")
            and "business_object_attributes" in normalized_statement
        ):
            attribute_select_count += 1

    sync_engine = db_session.bind.sync_engine
    event.listen(sync_engine, "before_cursor_execute", count_attribute_selects)
    try:
        snapshot = await build_project_snapshot(project.id, workspace.id, db_session)
    finally:
        event.remove(
            sync_engine,
            "before_cursor_execute",
            count_attribute_selects,
        )

    assert [item["name"] for item in snapshot["business_objects"]] == [
        "订单",
        "客户",
    ]
    assert [
        attribute["name"]
        for attribute in snapshot["business_objects"][0][
            "business_object_attributes"
        ]
    ] == ["订单编号", "金额"]
    assert [
        attribute["name"]
        for attribute in snapshot["business_objects"][1][
            "business_object_attributes"
        ]
    ] == ["客户名称", "客户编号"]
    assert attribute_select_count == 1


@pytest.mark.asyncio
async def test_build_project_snapshot_keeps_missing_project_error(db_session):
    with pytest.raises(ValueError, match="^project_not_found$"):
        await build_project_snapshot(999999, 1, db_session)
