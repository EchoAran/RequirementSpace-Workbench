from __future__ import annotations

import pytest
from backend.api.modules.project_lifecycle.schemas.project import (
    ProjectDetailResponse,
    ActorDetail,
    FeatureDetail,
    BusinessObjectDetail,
    BusinessObjectAttributeDetail,
    FlowDetail,
    FlowStepDetail,
    UnresolvedGateResponse,
    ScopeDetail,
    ScenarioDetail,
    AcceptanceCriterionDetail
)
from backend.integration.skill_backed_services.spl_syntax_export_service import SplSyntaxExportService
from backend.integration.skill_backed_services.spl_semantic_export_service import SplSemanticExportService
from datetime import datetime


@pytest.mark.asyncio
async def test_spl_syntax_export_scaffold():
    # Initialize the adapter service
    service = SplSyntaxExportService()
    
    # Construct a minimal project detail response
    detail = ProjectDetailResponse(
        project_id="test-project-uuid",
        project_name="Test Equipment Maintenance System",
        project_description="A test system for equipment maintenance.",
        user_requirements="User needs to manage maintenance tasks.",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )
    
    # Run export
    spl_text = await service.export(detail)
    
    # Verify the dummy/placeholder content is returned correctly
    assert "[DEFINE_AGENT: Agent_testproj" in spl_text
    assert "[DEFINE_PERSONA:]" in spl_text
    assert "Test Equipment Maintenance System" in spl_text
    assert "[END_AGENT]" in spl_text


@pytest.mark.asyncio
async def test_spl_syntax_export_rich():
    # Initialize the adapter service
    service = SplSyntaxExportService()
    
    now = datetime.now()
    
    # Construct a rich mock project detail response
    detail = ProjectDetailResponse(
        project_id="rich-project-uuid",
        project_name="企事业单位设备运维任务管理系统",
        project_description="系统面向企事业单位的设备和运维管理",
        user_requirements="需要维护设备数据库与维护人员数据库",
        actors=[
            ActorDetail(
                actor_id=1,
                actor_name="设备管理员",
                actor_description="负责设备信息录入与状态维护",
                updated_at=now
            )
        ],
        features=[
            FeatureDetail(
                feature_id=10,
                feature_name="维护设备基础信息",
                feature_description="录入与修改设备的关键基础信息",
                actor_ids=[1],
                parent_id=None,
                children_ids=[],
                scenarios=[],
                scope=None,  # No scope status to trigger missing_scope warning on leaf feature
                updated_at=now
            )
        ],
        business_objects=[
            BusinessObjectDetail(
                business_object_id=20,
                business_object_name="设备档案",
                business_object_description="记录设备的基础与状态属性",
                business_object_attributes=[
                    BusinessObjectAttributeDetail(
                        business_object_attribute_id=30,
                        business_object_attribute_name="device_code",
                        business_object_attribute_description="设备唯一编码",
                        business_object_attribute_type="string",
                        business_object_attribute_example="DEV-001",
                        updated_at=now
                    ),
                    BusinessObjectAttributeDetail(
                        business_object_attribute_id=31,
                        business_object_attribute_name="status_flag",
                        business_object_attribute_description="状态标识",
                        business_object_attribute_type="integer",
                        business_object_attribute_example="1",
                        updated_at=now
                    )
                ],
                updated_at=now
            )
        ],
        flows=[
            FlowDetail(
                flow_id=40,
                flow_name="设备基础信息维护流程",
                flow_description="管理员录入并保存设备档案 of 流程",
                feature_ids=[10],
                flow_steps=[
                    FlowStepDetail(
                        step_id=50,
                        step_name="录入设备基础信息",
                        step_description="管理员输入名称和编码",
                        step_type="actorAction",
                        position=1,
                        actor_ids=[1],
                        input_business_object_ids=[],
                        output_business_object_ids=[20],
                        updated_at=now
                    ),
                    FlowStepDetail(
                        step_id=51,
                        step_name="系统保存设备档案",
                        step_description="写入数据库并生成记录",
                        step_type="judgment",  # type judgment to test (judgment) description suffix
                        position=2,
                        actor_ids=[],
                        input_business_object_ids=[20],
                        output_business_object_ids=[20],
                        updated_at=now
                    )
                ],
                updated_at=now
            )
        ],
        unresolved_gates=[
            UnresolvedGateResponse(
                finding_id="gate_99",
                title="缺少场景",
                description="核心功能缺少验收场景",
                stage="stage2",
                code="WHAT_MISSING_SCENARIO"
            )
        ]
    )
    
    # Run export
    spl_text = await service.export(detail)
    
    # Assertions on output structure and details
    assert "[DEFINE_AGENT: Agent_richproj" in spl_text
    assert "[DEFINE_PERSONA:]" in spl_text
    assert "企事业单位设备运维任务管理系统" in spl_text
    
    # Check Actor
    assert "Actor_1: \"设备管理员: 负责设备信息录入与状态维护\"" in spl_text
    
    # Check Concept
    assert "ProjectDescription:" in spl_text
    assert "UserRequirements:" in spl_text
    
    # Check Constraint (Scope & Gate)
    # The leaf feature has no scope so it defaults to current, and triggers warning in export payload
    assert "DeliveryScope: \"Feature_10 维护设备基础信息 is current (本期).\"" in spl_text
    assert "ExportGate: \"Unresolved gate WHAT_MISSING_SCENARIO: 核心功能缺少验收场景\"" in spl_text
    
    # Check Business Object Types
    assert "BusinessObject 设备档案" in spl_text
    assert "BusinessObject_20 = {" in spl_text
    assert "device_code: text" in spl_text
    assert "status_flag: number" in spl_text
    
    # Check Variable (Feature Catalog)
    assert "\"Feature: 维护设备基础信息\"" in spl_text
    assert "READONLY Feature_10: text =" in spl_text
    assert "Parent: None" in spl_text
    assert "Scope: current" in spl_text
    
    # Check Worker
    assert "[DEFINE_WORKER: Flow_40]" in spl_text
    assert "COMMAND-1 [COMMAND ActorAction: 录入设备基础信息" in spl_text
    # Judgment step must render as SystemAction with (judgment) suffix
    assert "COMMAND-2 [COMMAND SystemAction: 系统保存设备档案 (judgment)" in spl_text
    assert "Actor: Actor_1" in spl_text
    assert "Output: BusinessObject_20" in spl_text
    assert "Input: BusinessObject_20" in spl_text
    assert "[END_WORKER]" in spl_text

    # Extract raw dictionary payload to test warning code missing_scope
    detail_dict = detail.model_dump()
    payload = {
        "project": {
            "project_id": detail_dict.get("project_id", ""),
            "project_name": detail_dict.get("project_name", ""),
            "project_description": detail_dict.get("project_description", ""),
            "user_requirements": detail_dict.get("user_requirements", ""),
        },
        "actors": detail_dict.get("actors", []),
        "features": detail_dict.get("features", []),
        "business_objects": detail_dict.get("business_objects", []),
        "flows": detail_dict.get("flows", []),
        "unresolved_gates": detail_dict.get("unresolved_gates", []),
        "export_options": {
            "mode": "syntax",
            "language": "zh-CN",
            "include_trace_links": True,
            "include_warnings": True,
        }
    }
    result = service._skill.export(payload)
    assert any(w["code"] == "missing_scope" and w["source"]["id"] == "10" for w in result["warnings"])


@pytest.mark.asyncio
async def test_spl_semantic_export_scaffold():
    # Initialize the adapter service
    service = SplSemanticExportService()
    
    # Mock LLM ask_json to return minimal mock data for scaffold test
    def mock_ask_json(prompt: str) -> dict:
        if "translating a database-backed" in prompt:
            return {
                "type_name": "DeviceArchive",
                "fields": []
            }
        elif "RequirementSpace business flow" in prompt:
            return {
                "worker_name": "DeviceMaintenanceFlow",
                "description": "Flow description",
                "actors": [],
                "inputs": [],
                "outputs": [],
                "main_flow_steps": []
            }
        elif "converting software acceptance" in prompt:
            return {
                "scenarios": []
            }
        elif "completeness and correctness" in prompt:
            return {
                "coverage_passed": True,
                "semantic_risks": []
            }
        return {}

    service._skill._ask_json = mock_ask_json

    # Construct a minimal project detail response
    detail = ProjectDetailResponse(
        project_id="test-project-uuid",
        project_name="Test Equipment Maintenance System",
        project_description="A test system for equipment maintenance.",
        user_requirements="User needs to manage maintenance tasks.",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[]
    )
    
    # Run export with optional llm_ctx
    spl_text = await service.export(detail, llm_ctx={"api_key": "test_key"})
    
    # Verify the dummy/placeholder content is returned correctly
    assert "[DEFINE_AGENT: Agent_testproj" in spl_text
    assert "[DEFINE_PERSONA:]" in spl_text
    assert "Test Equipment Maintenance System" in spl_text
    assert "[END_AGENT]" in spl_text


@pytest.mark.asyncio
async def test_spl_semantic_export_rich():
    # Initialize the adapter service
    service = SplSemanticExportService()
    
    now = datetime.now()
    
    # Construct a rich mock project detail response
    detail = ProjectDetailResponse(
        project_id="rich-project-uuid",
        project_name="企事业单位设备运维任务管理系统",
        project_description="系统面向企事业单位的设备和运维管理",
        user_requirements="需要维护设备数据库与维护人员数据库",
        actors=[
            ActorDetail(
                actor_id=1,
                actor_name="设备管理员",
                actor_description="负责设备信息录入与状态维护",
                updated_at=now
            )
        ],
        features=[
            FeatureDetail(
                feature_id=10,
                feature_name="维护设备基础信息",
                feature_description="录入与修改设备的关键基础信息",
                actor_ids=[1],
                parent_id=None,
                children_ids=[],
                scenarios=[
                    ScenarioDetail(
                        scenario_id=100,
                        scenario_name="录入正常设备信息",
                        scenario_content="输入合法数据生成档案",
                        feature_id=10,
                        actor_id=1,
                        acceptance_criteria=[
                            AcceptanceCriterionDetail(
                                criterion_id=200,
                                criterion_content="Given 管理员有权限，When 提交设备信息，Then 系统保存记录",
                                updated_at=now
                            )
                        ],
                        updated_at=now
                    )
                ],
                scope=ScopeDetail(
                    scope_id=1,
                    scope_status="current",
                    reason="本期核心功能",
                    updated_at=now
                ),
                updated_at=now
            )
        ],
        business_objects=[
            BusinessObjectDetail(
                business_object_id=20,
                business_object_name="设备档案",
                business_object_description="记录设备属性",
                business_object_attributes=[
                    BusinessObjectAttributeDetail(
                        business_object_attribute_id=30,
                        business_object_attribute_name="device_status",
                        business_object_attribute_description="设备状态",
                        business_object_attribute_type="string",
                        business_object_attribute_example="运行中",
                        updated_at=now
                    )
                ],
                updated_at=now
            )
        ],
        flows=[
            FlowDetail(
                flow_id=40,
                flow_name="设备基础信息维护流程",
                flow_description="管理员录入并保存设备档案",
                feature_ids=[10],
                flow_steps=[
                    FlowStepDetail(
                        step_id=50,
                        step_name="校验设备状态",
                        step_description="判断设备状态是否合法",
                        step_type="judgment",
                        position=1,
                        actor_ids=[1],
                        input_business_object_ids=[20],
                        output_business_object_ids=[],
                        updated_at=now
                    )
                ],
                updated_at=now
            )
        ],
        unresolved_gates=[]
    )

    # Mock the LLM ask_json responses to compile to rich semantic outputs
    def mock_ask_json(prompt: str) -> dict:
        if "translating a database-backed" in prompt:
            # Normalize BO device_status to include custom Enum
            return {
                "type_name": "DeviceArchive",
                "fields": [
                    {
                        "original_name": "device_status",
                        "normalized_name": "deviceStatus",
                        "spl_type": "DeviceRunStatus",
                        "is_enum": True,
                        "enum_candidates": ["running", "stopped", "faulty"],
                        "description": "设备运行状态",
                        "example": "running"
                    }
                ]
            }
        elif "RequirementSpace business flow" in prompt:
            # Map flow steps to nested tree judgment block
            return {
                "worker_name": "DeviceMaintenanceWorker",
                "description": "管理员维护设备信息的流程",
                "actors": ["Actor_1"],
                "inputs": ["DeviceArchive"],
                "outputs": ["DeviceArchive"],
                "main_flow_steps": [
                    {
                        "source_step_id": 50,
                        "step_type": "judgment",
                        "command_text": "系统判断设备状态是否合法",
                        "input_refs": ["DeviceArchive"],
                        "output_refs": [],
                        "decision_condition": "设备状态为合法运行状态",
                        "branch_kind": "if",
                        "sub_steps": [
                            {
                                "source_step_id": None,
                                "step_type": "systemAction",
                                "command_text": "SystemAction: 保存设备状态为正常 (running)",
                                "input_refs": [],
                                "output_refs": ["DeviceArchive"],
                                "decision_condition": None,
                                "branch_kind": "if",
                                "sub_steps": []
                            },
                            {
                                "source_step_id": None,
                                "step_type": "systemAction",
                                "command_text": "SystemAction: 拒绝保存并报错",
                                "input_refs": [],
                                "output_refs": [],
                                "decision_condition": None,
                                "branch_kind": "else",
                                "sub_steps": []
                            }
                        ]
                    }
                ]
            }
        elif "converting software acceptance" in prompt:
            # Return Gherkin Scenario with source_acceptance_criterion_ids mapped
            return {
                "scenarios": [
                    {
                        "source_scenario_id": 100,
                        "source_acceptance_criterion_ids": [200],
                        "scenario_name": "录入正常设备信息",
                        "flow_type": "normal",
                        "given": ["管理员有设备基础信息维护权限"],
                        "when": ["管理员提交新设备信息，且设备状态为running"],
                        "then": ["系统允许保存，生成新设备记录"]
                    }
                ]
            }
        elif "completeness and correctness" in prompt:
            return {
                "coverage_passed": True,
                "semantic_risks": ["无风险"]
            }
        return {}

    service._skill._ask_json = mock_ask_json

    # Run semantic export
    detail_dict = detail.model_dump()
    payload = {
        "project": {
            "project_id": detail_dict.get("project_id", ""),
            "project_name": detail_dict.get("project_name", ""),
            "project_description": detail_dict.get("project_description", ""),
            "user_requirements": detail_dict.get("user_requirements", ""),
        },
        "actors": detail_dict.get("actors", []),
        "features": detail_dict.get("features", []),
        "business_objects": detail_dict.get("business_objects", []),
        "flows": detail_dict.get("flows", []),
        "unresolved_gates": detail_dict.get("unresolved_gates", []),
        "export_options": {
            "mode": "semantic",
            "language": "zh-CN",
            "include_trace_links": True,
            "include_warnings": True,
        }
    }
    
    result = service._skill.export(payload)
    spl_text = result["spl_text"]

    # 1. Assert custom Enum is declared at the top of TYPES
    assert "DeviceRunStatus = [running, stopped, faulty]" in spl_text
    
    # 2. Assert structured type has normalized properties
    assert "BusinessObject DeviceArchive" in spl_text
    assert "DeviceArchive = {" in spl_text
    assert "deviceStatus: DeviceRunStatus" in spl_text

    # 3. Assert Worker has recursive nested IF block
    assert "[DEFINE_WORKER: DeviceMaintenanceWorker]" in spl_text
    assert "DECISION-1 [IF 设备状态为合法运行状态]" in spl_text
    assert "COMMAND-1 [COMMAND SystemAction: 保存设备状态为正常 (running)]" in spl_text
    assert "[ELSE]" in spl_text
    assert "COMMAND-2 [COMMAND SystemAction: 拒绝保存并报错]" in spl_text
    assert "END_IF" in spl_text

    # 4. Assert Scenario Gherkin
    assert "<EXPECTED-WORKER-BEHAVIOR-GHERKIN>" in spl_text
    assert "Scenario: \"录入正常设备信息\"" in spl_text
    assert "Given 管理员有设备基础信息维护权限" in spl_text
    assert "When 管理员提交新设备信息，且设备状态为running" in spl_text
    assert "Then 系统允许保存，生成新设备记录" in spl_text

    # 5. Assert Trace Links are properly registered
    trace_links = result["trace_links"]
    assert any(t["spl_ref"] == "DeviceArchive" and t["source_kind"] == "business_object" for t in trace_links)
    assert any(t["spl_ref"] == "Feature_100" and t["source_kind"] == "scenario" for t in trace_links)
    assert any(t["spl_ref"] == "AC_200" and t["source_kind"] == "acceptance_criterion" for t in trace_links)

    # 6. Test duplicate semantic identifier warning
    def mock_ask_json_duplicate(prompt: str) -> dict:
        if "translating a database-backed" in prompt:
            return {
                "type_name": "DeviceMaintenanceWorker",  # duplicate with flow worker name
                "fields": []
            }
        return mock_ask_json(prompt)
    
    service._skill._ask_json = mock_ask_json_duplicate
    result_dup = service._skill.export(payload)
    assert any(w["code"] == "duplicate_semantic_identifier" for w in result_dup["warnings"])
    assert result_dup["quality"] == "semantic_with_warnings"
    assert result_dup["coverage_report"]["coverage_passed"] is False

    # 7. Test judgment branch unresolved warning
    def mock_ask_json_unresolved(prompt: str) -> dict:
        if "RequirementSpace business flow" in prompt:
            return {
                "worker_name": "DeviceMaintenanceWorker",
                "description": "管理员维护设备信息的流程",
                "actors": ["Actor_1"],
                "inputs": [],
                "outputs": [],
                "main_flow_steps": [
                    {
                        "source_step_id": 50,
                        "step_type": "judgment",
                        "command_text": "系统判断设备状态是否合法",
                        "input_refs": [],
                        "output_refs": [],
                        "decision_condition": "设备状态为合法运行状态",
                        "branch_kind": "if",
                        "sub_steps": []  # empty sub_steps triggers judgment_branch_unresolved warning
                    }
                ]
            }
        return mock_ask_json(prompt)
    
    service._skill._ask_json = mock_ask_json_unresolved
    result_unres = service._skill.export(payload)
    assert any(w["code"] == "judgment_branch_unresolved" for w in result_unres["warnings"])
    assert result_unres["quality"] == "semantic_with_warnings"
    assert result_unres["coverage_report"]["coverage_passed"] is False
