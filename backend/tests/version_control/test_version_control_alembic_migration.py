"""
Real SQLite Alembic Migration Integration Tests for Version Control.
验证：
1. 真实 SQLite 数据库包含已有全量需求实体数据时，运行 `alembic upgrade head` 能顺利执行且不报 SQLite ALTER 约束错误；
2. 升级完成后自动为已有项目创建 main 分支、BranchWorkspace、初始化首个 Baseline Commit，并完成 12 个需求表 logical_uuid 与 workspace_id 的回填；
3. 数据库层面 `(workspace_id, logical_uuid)` 唯一性约束生效；
4. `alembic downgrade 57a2677fc6b9` 能够平滑卸载且保留基础旧数据。
"""
import os
import sqlite3
import pytest
from alembic.config import Config
from alembic import command


def bootstrap_full_57a2677fc6b9_schema(conn: sqlite3.Connection) -> None:
    """在 SQLite 中构建 57a2677fc6b9 版本的全量测试表与项目需求数据。"""
    cursor = conn.cursor()

    # 1. users & projects
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL,
            is_active BOOLEAN NOT NULL,
            preferred_locale VARCHAR(10) DEFAULT 'zh-CN',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE projects (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            public_id VARCHAR(36) NOT NULL UNIQUE,
            owner_user_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            content_locale VARCHAR(10),
            user_requirements TEXT NOT NULL,
            kano_status VARCHAR(50) NOT NULL,
            unlocked_stages VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # 2. 12 个需求实体与关系表（57a2677fc6b9 原生结构，无 logical_uuid 与 workspace_id）
    cursor.execute("""
        CREATE TABLE actors (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE features (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE feature_relations (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            parent_feature_id INTEGER NOT NULL,
            child_feature_id INTEGER NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(parent_feature_id) REFERENCES features (id) ON DELETE CASCADE,
            FOREIGN KEY(child_feature_id) REFERENCES features (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE feature_scopes (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            feature_id INTEGER NOT NULL UNIQUE,
            status VARCHAR(50) NOT NULL,
            positive_picture BLOB,
            negative_picture BLOB,
            positive_summary TEXT,
            negative_summary TEXT,
            reason TEXT NOT NULL,
            kano_category VARCHAR(50),
            kano_category_name VARCHAR(100),
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(feature_id) REFERENCES features (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE scenarios (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            feature_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            gherkin_spec_id INTEGER,
            gherkin_scenario_index INTEGER,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
            FOREIGN KEY(feature_id) REFERENCES features (id) ON DELETE CASCADE,
            FOREIGN KEY(actor_id) REFERENCES actors (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE scenario_acceptance_criteria (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            scenario_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            content TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE business_objects (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE business_object_attributes (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            business_object_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            data_type VARCHAR(100) NOT NULL,
            example TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(business_object_id) REFERENCES business_objects (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE flows (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE flow_steps (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            flow_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            step_type VARCHAR(50) NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(flow_id) REFERENCES flows (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE choice_groups (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            slot_id INTEGER,
            status VARCHAR(50) NOT NULL DEFAULT 'open',
            selection_mode VARCHAR(50) NOT NULL DEFAULT 'single',
            source_type VARCHAR(50),
            source_id VARCHAR(200),
            issue_code VARCHAR(100),
            issue_id VARCHAR(200),
            stage VARCHAR(20),
            target TEXT,
            context_hash VARCHAR(64),
            generation_type VARCHAR(80),
            origin_endpoint VARCHAR(200),
            candidate_count INTEGER,
            success_count INTEGER,
            failure_count INTEGER,
            status_detail TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE choices (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            choice_group_id INTEGER NOT NULL,
            title VARCHAR(255) NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            status VARCHAR(50) NOT NULL DEFAULT 'candidate',
            patch TEXT NOT NULL,
            impact_preview TEXT,
            payload TEXT,
            draft_type VARCHAR(80),
            apply_mode VARCHAR(50) NOT NULL DEFAULT 'patch',
            preview TEXT,
            score FLOAT,
            validation_report TEXT,
            error TEXT,
            strategy_id VARCHAR(100),
            strategy_label VARCHAR(255),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(choice_group_id) REFERENCES choice_groups (id) ON DELETE CASCADE
        )
    """)

    # 3. alembic_version 置为 57a2677fc6b9
    cursor.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
    cursor.execute("INSERT INTO alembic_version (version_num) VALUES ('57a2677fc6b9')")

    # 4. 插入既有历史测试数据
    cursor.execute(
        "INSERT INTO users (id, email, password_hash, role, is_active, created_at, updated_at) "
        "VALUES (1, 'admin@example.com', 'hash', 'admin', 1, '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO projects (id, public_id, owner_user_id, name, description, user_requirements, kano_status, unlocked_stages, created_at, updated_at) "
        "VALUES (100, 'proj_uuid_100', 1, 'E-Commerce System', 'Desc', 'Requirements text', 'completed', 'stage1', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO actors (id, project_id, name, description, created_at, updated_at) "
        "VALUES (10, 100, 'Buyer', 'End buyer', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO features (id, project_id, name, description, created_at, updated_at) "
        "VALUES (20, 100, 'Checkout Feature', 'Order payment', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO feature_relations (id, parent_feature_id, child_feature_id, position, created_at, updated_at) "
        "VALUES (30, 20, 20, 0, '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO feature_scopes (id, feature_id, status, reason, created_at, updated_at) "
        "VALUES (40, 20, 'current', 'Must have', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO scenarios (id, project_id, feature_id, actor_id, name, content, created_at, updated_at) "
        "VALUES (50, 100, 20, 10, 'Pay with Credit Card', 'Given buyer is on cart', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO scenario_acceptance_criteria (id, scenario_id, position, content, created_at, updated_at) "
        "VALUES (60, 50, 1, 'Payment succeeds within 3s', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO business_objects (id, project_id, name, description, created_at, updated_at) "
        "VALUES (70, 100, 'Order', 'Purchase order', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO business_object_attributes (id, business_object_id, name, description, data_type, example, created_at, updated_at) "
        "VALUES (80, 70, 'total_price', 'Amount', 'number', '99.9', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO flows (id, project_id, name, description, created_at, updated_at) "
        "VALUES (90, 100, 'Checkout Flow', 'Step-by-step', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO flow_steps (id, flow_id, position, name, description, step_type, created_at, updated_at) "
        "VALUES (100, 90, 1, 'Click Pay', 'Initiate payment', 'user_action', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO choice_groups (id, project_id, status, created_at, updated_at) "
        "VALUES (110, 100, 'open', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )
    cursor.execute(
        "INSERT INTO choices (id, choice_group_id, title, patch, created_at, updated_at) "
        "VALUES (120, 110, 'Choice A', '{}', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
    )

    conn.commit()


def test_real_sqlite_alembic_upgrade_and_downgrade_flow(tmp_path):
    """测试真实 SQLite 数据库升级至 20260730_200000 并在 Upgrade 中自动完成基线初始化。"""
    db_file = tmp_path / "real_sqlite_version_control_test.db"
    sync_url = f"sqlite:///{db_file}"

    # 1. 构建全量既有 57a2677fc6b9 数据库
    conn = sqlite3.connect(str(db_file))
    bootstrap_full_57a2677fc6b9_schema(conn)
    conn.close()

    # 2. 配置 Alembic
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

    # 3. 运行 alembic upgrade head (包含批处理 ALTER 以及自动基线回填)
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = sync_url
    try:
        command.upgrade(alembic_cfg, "head")

        # 4. 验证升级后的数据库结构与自动基线数据
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        # 4.1 校验 main 分支与 BranchWorkspace
        cursor.execute("SELECT id, name, is_protected, is_default FROM requirement_branches WHERE project_id=100")
        branch_row = cursor.fetchone()
        assert branch_row is not None
        assert branch_row[1] == "main"
        assert branch_row[2] == 1  # is_protected
        assert branch_row[3] == 1  # is_default

        cursor.execute("SELECT id FROM branch_workspaces WHERE project_id=100 AND branch_id=?", (branch_row[0],))
        ws_row = cursor.fetchone()
        assert ws_row is not None
        workspace_id = ws_row[0]

        # 4.2 校验 Baseline Commit
        cursor.execute("SELECT id, state_hash, message FROM requirement_commits WHERE project_id=100")
        commit_row = cursor.fetchone()
        assert commit_row is not None
        assert len(commit_row[1]) == 64  # SHA-256 state_hash
        assert "baseline" in commit_row[2].lower()

        # 4.3 校验 12 个实体表的 workspace_id 与 logical_uuid 已被全量补齐
        target_tables = [
            "actors", "features", "feature_relations", "feature_scopes",
            "scenarios", "scenario_acceptance_criteria", "business_objects",
            "business_object_attributes", "flows", "flow_steps",
            "choice_groups", "choices"
        ]
        for tbl in target_tables:
            cursor.execute(f"SELECT logical_uuid, workspace_id FROM {tbl}")
            rows = cursor.fetchall()
            assert len(rows) > 0, f"Table {tbl} should have populated rows"
            for row in rows:
                assert row[0] is not None and len(row[0]) == 36, f"Table {tbl} logical_uuid should be valid UUID"
                assert row[1] == workspace_id, f"Table {tbl} workspace_id should be backfilled to main workspace"

        # 4.35 校验提交列表分页复合索引存在（Phase A）
        cursor.execute("PRAGMA index_list('requirement_commits')")
        index_names = [row[1] for row in cursor.fetchall()]
        assert "ix_requirement_commits_project_created_id" in index_names

        # 4.4 校验 (workspace_id, logical_uuid) 数据库级 Unique 约束
        cursor.execute("SELECT logical_uuid FROM actors WHERE id=10")
        actor_uuid = cursor.fetchone()[0]

        # 企图在同一 workspace_id 插入相同 logical_uuid，必须触发 sqlite3.IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO actors (project_id, workspace_id, logical_uuid, name, description, created_at, updated_at) "
                "VALUES (100, ?, ?, 'Duplicate Actor', '', '2026-07-15 00:00:00', '2026-07-15 00:00:00')",
                (workspace_id, actor_uuid)
            )

        conn.close()

        # 5. 测试 alembic downgrade 57a2677fc6b9
        command.downgrade(alembic_cfg, "57a2677fc6b9")

        # 6. 验证降级后旧数据无损且新增表/字段已平滑擦除
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='requirement_branches'")
        assert cursor.fetchone() is None

        cursor.execute("PRAGMA table_info(actors)")
        actor_cols = [c[1] for c in cursor.fetchall()]
        assert "logical_uuid" not in actor_cols
        assert "workspace_id" not in actor_cols

        cursor.execute("SELECT name FROM actors WHERE id=10")
        assert cursor.fetchone()[0] == "Buyer"

        conn.close()

    finally:
        if old_db_url is not None:
            os.environ["DATABASE_URL"] = old_db_url


def test_sqlite_alembic_logical_uuid_not_null_enforcement(tmp_path):
    """验证 Upgrade head 完成后，数据库层拒绝插入 logical_uuid 为 NULL 的实体记录。"""
    db_file = tmp_path / "not_null_enforcement_test.db"
    sync_url = f"sqlite:///{db_file}"

    conn = sqlite3.connect(str(db_file))
    bootstrap_full_57a2677fc6b9_schema(conn)
    conn.close()

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = sync_url
    try:
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        # 试图在 actors 表中插入 logical_uuid = NULL，必须触发 NOT NULL constraint failed
        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
            cursor.execute(
                "INSERT INTO actors (project_id, workspace_id, logical_uuid, name, description, created_at, updated_at) "
                "VALUES (100, 1, NULL, 'Null UUID Actor', 'Desc', '2026-07-15 00:00:00', '2026-07-15 00:00:00')"
            )

        conn.close()
    finally:
        if old_db_url is not None:
            os.environ["DATABASE_URL"] = old_db_url


def test_sqlite_alembic_rollback_on_step8_failure(tmp_path, monkeypatch):
    """验证当基线分支/工作区已创建但后续步骤（如步骤 8 NOT NULL 约束收紧）失败时，Alembic 外层事务全量回滚，不留残留状态。"""
    from alembic.operations import Operations

    db_file = tmp_path / "rollback_on_step8_failure_test.db"
    sync_url = f"sqlite:///{db_file}"

    conn = sqlite3.connect(str(db_file))
    bootstrap_full_57a2677fc6b9_schema(conn)
    conn.close()

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

    orig_batch_alter = Operations.batch_alter_table
    call_count = 0

    def mock_batch_alter(self, table_name, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 12:
            raise RuntimeError("Simulated step 8 alteration failure")
        return orig_batch_alter(self, table_name, *args, **kwargs)

    monkeypatch.setattr(Operations, "batch_alter_table", mock_batch_alter)

    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = sync_url
    try:
        with pytest.raises(RuntimeError, match="Simulated step 8 alteration failure"):
            command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        cursor.execute("SELECT version_num FROM alembic_version")
        assert cursor.fetchone()[0] == "57a2677fc6b9"

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='requirement_branches'")
        assert cursor.fetchone() is None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='requirement_commits'")
        assert cursor.fetchone() is None

        cursor.execute("PRAGMA table_info(actors)")
        cols = [c[1] for c in cursor.fetchall()]
        assert "logical_uuid" not in cols

        conn.close()
    finally:
        if old_db_url is not None:
            os.environ["DATABASE_URL"] = old_db_url


def test_git_graph_validations(sync_db_session):
    """验证直接、间接环路（防环约束）以及跨项目引用（外键与 head/parent）约束在数据库 ORM/校验层的生效。"""
    from backend.database.model import ProjectModel, RequirementCommitModel, RequirementBranchModel, RequirementCommitParentModel
    from backend.api.modules.version_control.ports import SQLAlchemyGitGraphValidator
    
    # 0. 构造基础 Project
    p1 = ProjectModel(id=1, name="Project 1", description="Proj 1")
    p2 = ProjectModel(id=2, name="Project 2", description="Proj 2")
    sync_db_session.add_all([p1, p2])
    sync_db_session.commit()

    # 1. 构造基础 Commit
    c_a1 = RequirementCommitModel(id=201, project_id=1, message="Commit A1", state_json="{}", state_hash="hash1")
    c_b1 = RequirementCommitModel(id=202, project_id=2, message="Commit B1", state_json="{}", state_hash="hash2")
    sync_db_session.add_all([c_a1, c_b1])
    sync_db_session.commit()

    # 2. 测试跨项目分支 head 引用校验
    branch = RequirementBranchModel(project_id=1, name="branch-a", head_commit_id=202) # Project 1 head points to Commit B1 (Project 2)
    sync_db_session.add(branch)
    with pytest.raises(ValueError, match="Branch head commit must belong to the same project"):
        sync_db_session.commit()
    sync_db_session.rollback()

    # 3. 测试跨项目 parent 引用校验
    parent_rel = RequirementCommitParentModel(commit_id=201, parent_commit_id=202)
    sync_db_session.add(parent_rel)
    with pytest.raises(ValueError, match="Parent and child commits must belong to the same project"):
        sync_db_session.commit()
    sync_db_session.rollback()

    # 4. 测试直接自环校验
    self_loop = RequirementCommitParentModel(commit_id=201, parent_commit_id=201)
    sync_db_session.add(self_loop)
    with pytest.raises(ValueError, match="self-loop"):
        sync_db_session.commit()
    sync_db_session.rollback()

    # 5. 测试间接环路（Cycle）校验
    c_a2 = RequirementCommitModel(id=203, project_id=1, message="Commit A2", state_json="{}", state_hash="hash3")
    c_a3 = RequirementCommitModel(id=204, project_id=1, message="Commit A3", state_json="{}", state_hash="hash4")
    sync_db_session.add_all([c_a2, c_a3])
    sync_db_session.commit()

    rel1 = RequirementCommitParentModel(commit_id=204, parent_commit_id=203) # A3 -> A2
    rel2 = RequirementCommitParentModel(commit_id=203, parent_commit_id=201) # A2 -> A1
    sync_db_session.add_all([rel1, rel2])
    sync_db_session.commit()

    # 尝试添加 A1 -> A3 (使得 A1 -> A3 -> A2 -> A1 形成间接环路)
    rel3 = RequirementCommitParentModel(commit_id=201, parent_commit_id=204)
    sync_db_session.add(rel3)
    with pytest.raises(ValueError, match="Cycle detected"):
        sync_db_session.commit()
    sync_db_session.rollback()

    # 6. 测试 IGitGraphValidator 接口直接校验
    validator = SQLAlchemyGitGraphValidator()
    # 正常无环跨项目抛错
    with pytest.raises(ValueError, match="Parent and child commits must belong to the same project"):
        validator.validate_commit_parent(sync_db_session, 201, 202)
    
    # 正常无自环校验
    with pytest.raises(ValueError, match="self-loop"):
        validator.validate_commit_parent(sync_db_session, 201, 201)


