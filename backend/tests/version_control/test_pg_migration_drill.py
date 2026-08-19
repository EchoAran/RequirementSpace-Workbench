"""
PostgreSQL Migration Drill Test (Phase 7, conditional).

仅在 DATABASE_URL 指向 PostgreSQL 时运行。测试在目标数据库上**自举**与 SQLite 演练等价的历史
schema 与业务数据（57a2677fc6b9 版本，无 logical_uuid/workspace_id），再执行 alembic upgrade head，
验证 PG 上迁移、基线创建与 12 个实体表回填与 SQLite 一致，且项目 ID 动态取自自举数据而非硬编码。

危险提示：本测试会直接修改 DATABASE_URL 指向的数据库（先建旧 schema/数据，再 upgrade head + 回填），
只允许对一次性/隔离的测试库执行，绝不可指向生产库。
"""
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config

BASE_REV = "57a2677fc6b9"


def _postgres_url() -> str | None:
    url = (os.getenv("DATABASE_URL") or "").strip().strip("'\" ")
    return url if url.lower().startswith("postgres") else None


def _sync_url(url: str) -> str:
    """把 async PG URL 归一化为 psycopg 同步 URL（与 alembic/env.py 一致）。"""
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")


def _bootstrap_legacy_schema(engine) -> int:
    """在空数据库中自举 57a2677fc6b9 版本的历史 schema 与业务数据，返回 project_id。

    表结构与 SQLite 演练测试的 bootstrap_full_57a2677fc6b9_schema 等价，仅适配 PG 类型。
    幂等：若已存在 alembic_version 表则跳过（避免重复执行破坏数据）。
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        has_alembic = conn.execute(
            text("SELECT to_regclass('public.alembic_version')")
        ).scalar()
        if has_alembic:
            return _existing_project_id(conn)

        def _create(table, cols):
            conn.execute(text(f"CREATE TABLE {table} ({cols})"))

        _create("users", """
            id SERIAL PRIMARY KEY, email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL, role VARCHAR(50) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            preferred_locale VARCHAR(10) DEFAULT 'zh-CN',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("projects", """
            id SERIAL PRIMARY KEY, public_id VARCHAR(36) NOT NULL UNIQUE,
            owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL, description TEXT NOT NULL,
            content_locale VARCHAR(10), user_requirements TEXT NOT NULL,
            kano_status VARCHAR(50) NOT NULL, unlocked_stages VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("actors", """
            id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL, description TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("features", """
            id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL, description TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("feature_relations", """
            id SERIAL PRIMARY KEY,
            parent_feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
            child_feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
            position INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("feature_scopes", """
            id SERIAL PRIMARY KEY, feature_id INTEGER NOT NULL UNIQUE REFERENCES features(id) ON DELETE CASCADE,
            status VARCHAR(50) NOT NULL, positive_picture BYTEA, negative_picture BYTEA,
            positive_summary TEXT, negative_summary TEXT, reason TEXT NOT NULL,
            kano_category VARCHAR(50), kano_category_name VARCHAR(100),
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("scenarios", """
            id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
            actor_id INTEGER NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL, content TEXT NOT NULL,
            gherkin_spec_id INTEGER, gherkin_scenario_index INTEGER,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("scenario_acceptance_criteria", """
            id SERIAL PRIMARY KEY, scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
            position INTEGER NOT NULL, content TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("business_objects", """
            id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL, description TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("business_object_attributes", """
            id SERIAL PRIMARY KEY, business_object_id INTEGER NOT NULL REFERENCES business_objects(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL, description TEXT NOT NULL, data_type VARCHAR(100) NOT NULL,
            example TEXT NOT NULL, confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("flows", """
            id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL, description TEXT NOT NULL,
            confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("flow_steps", """
            id SERIAL PRIMARY KEY, flow_id INTEGER NOT NULL REFERENCES flows(id) ON DELETE CASCADE,
            position INTEGER NOT NULL, name VARCHAR(255) NOT NULL, description TEXT NOT NULL,
            step_type VARCHAR(50) NOT NULL, confirmation_status VARCHAR(20) NOT NULL DEFAULT 'ai_assumption',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("choice_groups", """
            id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            slot_id INTEGER, status VARCHAR(50) NOT NULL DEFAULT 'open',
            selection_mode VARCHAR(50) NOT NULL DEFAULT 'single', source_type VARCHAR(50),
            source_id VARCHAR(200), issue_code VARCHAR(100), issue_id VARCHAR(200),
            stage VARCHAR(20), target TEXT, context_hash VARCHAR(64),
            generation_type VARCHAR(80), origin_endpoint VARCHAR(200),
            candidate_count INTEGER, success_count INTEGER, failure_count INTEGER, status_detail TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        _create("choices", """
            id SERIAL PRIMARY KEY, choice_group_id INTEGER NOT NULL REFERENCES choice_groups(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL, rationale TEXT NOT NULL DEFAULT '',
            status VARCHAR(50) NOT NULL DEFAULT 'candidate', patch TEXT NOT NULL,
            impact_preview TEXT, payload TEXT, draft_type VARCHAR(80),
            apply_mode VARCHAR(50) NOT NULL DEFAULT 'patch', preview TEXT,
            score FLOAT, validation_report TEXT, error TEXT,
            strategy_id VARCHAR(100), strategy_label VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """)
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{BASE_REV}')"))

        # 业务数据：单个项目 + 各实体一行，project_id 动态生成并返回。
        user_id = conn.execute(text(
            "INSERT INTO users (email, password_hash, role) VALUES ('admin@example.com', 'hash', 'admin') RETURNING id"
        )).scalar()
        project_id = conn.execute(text(
            "INSERT INTO projects (public_id, owner_user_id, name, description, user_requirements, kano_status, unlocked_stages) "
            "VALUES (:pid, :owner, 'E-Commerce System', 'Desc', 'Requirements text', 'completed', 'stage1') RETURNING id"
        ), {"pid": str(uuid.uuid4()), "owner": user_id}).scalar()

        feature_id = conn.execute(text(
            "INSERT INTO features (project_id, name, description) VALUES (:p, 'Checkout Feature', 'Order payment') RETURNING id"
        ), {"p": project_id}).scalar()
        actor_id = conn.execute(text(
            "INSERT INTO actors (project_id, name, description) VALUES (:p, 'Buyer', 'End buyer') RETURNING id"
        ), {"p": project_id}).scalar()
        conn.execute(text(
            "INSERT INTO feature_relations (parent_feature_id, child_feature_id, position) VALUES (:p, :c, 0)"
        ), {"p": feature_id, "c": feature_id})
        conn.execute(text(
            "INSERT INTO feature_scopes (feature_id, status, reason) VALUES (:f, 'current', 'Must have')"
        ), {"f": feature_id})
        scenario_id = conn.execute(text(
            "INSERT INTO scenarios (project_id, feature_id, actor_id, name, content) "
            "VALUES (:p, :f, :a, 'Pay with Credit Card', 'Given buyer is on cart') RETURNING id"
        ), {"p": project_id, "f": feature_id, "a": actor_id}).scalar()
        conn.execute(text(
            "INSERT INTO scenario_acceptance_criteria (scenario_id, position, content) VALUES (:s, 1, 'Payment succeeds within 3s')"
        ), {"s": scenario_id})
        bo_id = conn.execute(text(
            "INSERT INTO business_objects (project_id, name, description) VALUES (:p, 'Order', 'Purchase order') RETURNING id"
        ), {"p": project_id}).scalar()
        conn.execute(text(
            "INSERT INTO business_object_attributes (business_object_id, name, description, data_type, example) "
            "VALUES (:b, 'total_price', 'Amount', 'number', '99.9')"
        ), {"b": bo_id})
        flow_id = conn.execute(text(
            "INSERT INTO flows (project_id, name, description) VALUES (:p, 'Checkout Flow', 'Step-by-step') RETURNING id"
        ), {"p": project_id}).scalar()
        conn.execute(text(
            "INSERT INTO flow_steps (flow_id, position, name, description, step_type) "
            "VALUES (:f, 1, 'Click Pay', 'Initiate payment', 'user_action')"
        ), {"f": flow_id})
        cg_id = conn.execute(text(
            "INSERT INTO choice_groups (project_id, status) VALUES (:p, 'open') RETURNING id"
        ), {"p": project_id}).scalar()
        conn.execute(text(
            "INSERT INTO choices (choice_group_id, title, patch) VALUES (:c, 'Choice A', '{}')"
        ), {"c": cg_id})
        return project_id


def _existing_project_id(conn) -> int:
    from sqlalchemy import text
    return conn.execute(text("SELECT id FROM projects ORDER BY id LIMIT 1")).scalar()


@pytest.mark.skipif(
    not _postgres_url(),
    reason="DATABASE_URL is not a postgres URL; skip PG migration drill",
)
def test_pg_upgrade_and_backfill():
    """在空隔离 PG 上自举旧 schema/数据 → upgrade head → 验证基线创建与 12 表回填。"""
    url = _postgres_url()

    from sqlalchemy import create_engine, text
    engine = create_engine(_sync_url(url))

    # 1. 自举历史 schema 与数据（幂等：已存在则复用），动态获取 project_id。
    project_id = _bootstrap_legacy_schema(engine)
    assert project_id is not None

    # 2. alembic upgrade head（迁移 + 基线回填）。
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _sync_url(url))
    command.upgrade(cfg, "head")

    # 3. 校验基线数据（project_id 动态，不硬编码）。
    with engine.connect() as conn:
        branch_rows = conn.execute(
            text("SELECT id, name, is_protected, is_default FROM requirement_branches WHERE project_id=:p"),
            {"p": project_id},
        ).fetchall()
        assert len(branch_rows) == 1
        assert branch_rows[0][1] == "main"
        assert bool(branch_rows[0][2]) is True
        assert bool(branch_rows[0][3]) is True

        commit_count = conn.execute(
            text("SELECT COUNT(*) FROM requirement_commits WHERE project_id=:p"),
            {"p": project_id},
        ).scalar()
        assert commit_count == 1

        for table in ("actors", "features", "feature_relations", "feature_scopes",
                      "scenarios", "scenario_acceptance_criteria", "business_objects",
                      "business_object_attributes", "flows", "flow_steps",
                      "choice_groups", "choices"):
            rows = conn.execute(text(f"SELECT logical_uuid, workspace_id FROM {table}")).fetchall()
            assert len(rows) > 0, f"Table {table} should be backfilled on PG"
            for logical_uuid, workspace_id in rows:
                assert logical_uuid and len(logical_uuid) == 36
                assert workspace_id is not None
    engine.dispose()
