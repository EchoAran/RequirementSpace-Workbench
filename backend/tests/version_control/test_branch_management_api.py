"""
Unit & Integration tests for Version Control Branch Management APIs & Application Service.
"""
import pytest

from backend.api.modules.version_control.application.clean_initialization import (
    initialize_project_version_control,
)
from backend.api.modules.version_control.application.branch_service import (
    create_branch,
    delete_branch,
    list_branches,
    rename_branch,
    resolve_branch_context,
)
from backend.api.modules.version_control.schemas import (
    BranchCreateRequest,
    BranchUpdateRequest,
)


def test_branch_lifecycle(sync_db_session, seeded_project):
    """测试分支的完整生命周期：基线解析 -> 创建新分支 -> 重命名 -> 删除拦截 -> 删除成功。"""
    # 1. 初始化基线
    initialize_project_version_control(sync_db_session, seeded_project)

    # 2. 校验 main 分支解析
    branch, ws, perms = resolve_branch_context(sync_db_session, seeded_project.id, branch_ref=None)
    assert branch is not None
    assert branch.name == "main"
    assert ws is not None
    assert perms["can_delete"] is False

    # 3. 创建新分支 feature/test-1
    req = BranchCreateRequest(
        name="feature/test-1",
        description="A test feature branch",
        source_branch_public_id="main",
    )
    new_b = create_branch(sync_db_session, seeded_project.id, req, user_id=seeded_project.owner_user_id)
    assert new_b.name == "feature/test-1"
    assert new_b.permissions.can_delete is True

    # 4. 获取分支列表
    all_b = list_branches(sync_db_session, seeded_project.id)
    assert len(all_b) == 2
    names = [b.name for b in all_b]
    assert "main" in names
    assert "feature/test-1" in names

    # 5. 重命名 feature/test-1 -> feature/test-renamed
    upd_req = BranchUpdateRequest(name="feature/test-renamed")
    renamed_b = rename_branch(sync_db_session, seeded_project.id, new_b.public_id, upd_req, user_id=seeded_project.owner_user_id)
    assert renamed_b.name == "feature/test-renamed"

    # 6. 尝试重命名 main (应抛出 Permission/ValueError)
    with pytest.raises(ValueError, match="Cannot rename protected"):
        rename_branch(sync_db_session, seeded_project.id, branch.public_id, BranchUpdateRequest(name="new-main"), user_id=seeded_project.owner_user_id)

    # 7. 尝试删除 main (应抛出 Permission/ValueError)
    with pytest.raises(ValueError, match="Cannot delete protected or default main branch"):
        delete_branch(sync_db_session, seeded_project.id, branch.public_id, user_id=seeded_project.owner_user_id)

    # 8. 删除新分支 feature/test-renamed
    del_res = delete_branch(sync_db_session, seeded_project.id, renamed_b.public_id, user_id=seeded_project.owner_user_id)
    assert del_res["status"] == "success"

    all_b_after = list_branches(sync_db_session, seeded_project.id)
    assert len(all_b_after) == 1
