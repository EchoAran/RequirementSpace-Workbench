from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import Base, SessionLocal, engine, get_db
from .seed import build_seed_ir


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        exists = db.query(models.Workspace).first()
        if not exists:
            seed = build_seed_ir()
            crud.upsert_workspace_from_ir(db, seed)
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="RequirementSpace Workbench API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/workspaces", response_model=list[schemas.WorkspaceListItem])
def list_workspaces(db: Session = Depends(get_db)):
    items = db.query(models.Workspace).order_by(models.Workspace.updated_at.desc()).all()
    res = []
    for i in items:
        issue_count = db.query(models.Issue).filter(models.Issue.workspace_id == i.id, models.Issue.status == 'open').count()
        node_count = db.query(models.Node).filter(models.Node.workspace_id == i.id).count()
        
        if issue_count > 0:
            status = "待确认缺口"
        elif node_count > 0:
            status = "设计中"
        else:
            status = "草稿"
            
        res.append(
            schemas.WorkspaceListItem(
                id=i.id, 
                name=i.name, 
                idea=i.idea, 
                updatedAt=i.updated_at.isoformat(),
                status=status,
                issueCount=issue_count,
                nodeCount=node_count
            )
        )
    return res


@app.post("/api/workspaces/bootstrap")
def bootstrap_workspace(req: schemas.WorkspaceBootstrapRequest, db: Session = Depends(get_db)):
    ir = build_seed_ir(req.prompt)
    ir["id"] = f"rs_{uuid.uuid4().hex[:10]}"
    ir["name"] = "新建需求探索项目"
    ws = crud.upsert_workspace_from_ir(db, ir)
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.get("/api/workspaces/default")
def get_default_workspace(db: Session = Depends(get_db)):
    ws = db.query(models.Workspace).order_by(models.Workspace.updated_at.desc()).first()
    if not ws:
        seed = build_seed_ir()
        ws = crud.upsert_workspace_from_ir(db, seed)
        db.commit()
        db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.get("/api/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    return crud.serialize_workspace(ws)


@app.patch("/api/workspaces/{workspace_id}/nodes/{node_id}")
def patch_node(workspace_id: str, node_id: str, req: schemas.NodeUpdateRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.update_node(db, ws, node_id, req.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.patch("/api/workspaces/{workspace_id}/nodes/{node_id}/status")
def patch_node_status(workspace_id: str, node_id: str, req: schemas.StatusUpdateRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.update_node(db, ws, node_id, {"status": req.status})
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.patch("/api/workspaces/{workspace_id}/nodes/{node_id}/scope")
def patch_node_scope(workspace_id: str, node_id: str, req: schemas.ScopeUpdateRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.move_scope(db, ws, node_id, req.scopeStatus)
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.patch("/api/workspaces/{workspace_id}/issues/{issue_id}")
def patch_issue_status(workspace_id: str, issue_id: str, req: schemas.IssueStatusRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.update_issue_status(db, ws, issue_id, req.status)
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.post("/api/workspaces/{workspace_id}/issues/{issue_id}/generate-candidate")
def generate_candidate(workspace_id: str, issue_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    result = crud.generate_candidate_for_issue(db, ws, issue_id)
    db.commit()
    db.refresh(ws)
    return {"result": result, "workspace": crud.serialize_workspace(ws)}


@app.post("/api/workspaces/{workspace_id}/choices/{choice_id}/accept")
def accept_choice(workspace_id: str, choice_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.accept_choice(db, ws, choice_id)
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.post("/api/workspaces/{workspace_id}/choices/{choice_id}/reject")
def reject_choice(workspace_id: str, choice_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.reject_choice(db, ws, choice_id)
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.post("/api/workspaces/{workspace_id}/diagnose")
def diagnose(workspace_id: str, _: schemas.DiagnoseRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    result = crud.run_diagnosis(db, ws)
    db.commit()
    db.refresh(ws)
    return {"result": result, "workspace": crud.serialize_workspace(ws)}


@app.post("/api/workspaces/{workspace_id}/patch")
def apply_patch(workspace_id: str, patch: schemas.GraphPatch, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.apply_graph_patch(db, ws, patch.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.post("/api/workspaces/{workspace_id}/issues")
def create_issue(workspace_id: str, req: schemas.CreateIssueRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    issue_id = crud.create_issue(db, ws, req.model_dump())
    db.commit()
    db.refresh(ws)
    return {"issueId": issue_id, "workspace": crud.serialize_workspace(ws)}


@app.post("/api/workspaces/{workspace_id}/choice-groups/{choice_group_id}/choices")
def add_choice(workspace_id: str, choice_group_id: str, req: schemas.AddChoiceRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    choice_id = crud.add_choice_to_group(db, ws, choice_group_id, req.model_dump())
    db.commit()
    db.refresh(ws)
    return {"choiceId": choice_id, "workspace": crud.serialize_workspace(ws)}


@app.get("/api/workspaces/{workspace_id}/export")
def export_workspace(workspace_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    return crud.serialize_workspace(ws)


@app.post("/api/prompts/analyze", response_model=schemas.PromptAnalyzeResponse)
def analyze_prompt(req: schemas.PromptAnalyzeRequest):
    prompt = req.prompt.strip()
    task_type = "需求探索"
    if "请假" in prompt or "审批" in prompt:
        task_type = "企业内部审批流管理应用"
    elif "CRM" in prompt:
        task_type = "销售流程管理应用"
    elif "看板" in prompt:
        task_type = "项目进度与风险管理工具"

    return schemas.PromptAnalyzeResponse(
        taskType=task_type,
        goals=["明确核心目标与可衡量标准", "尽快形成单版本需求空间并可验证"],
        actors=["业务发起人", "最终用户", "系统/管理员"],
        flows=["主流程闭环", "异常分支与回滚", "通知与归档"],
        objects=["关键业务对象 (Stateful)", "权限与角色模型"],
        questions=[
            "目标：你希望用什么指标判断成功？",
            "范围：哪些能力明确不做或延期？",
            "流程：异常/退回/撤销是否需要？",
        ],
    )


@app.get("/", include_in_schema=False)
def serve_root():
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    return HTMLResponse(
        "<h3>RequirementSpace Workbench</h3>"
        "<p>前端未构建或 dist 不存在。请在 frontend 目录运行 npm run dev，然后打开对应的 Local 地址。</p>",
        status_code=200,
    )


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    if full_path.startswith("api") or full_path in {"docs", "redoc", "openapi.json"}:
        raise HTTPException(status_code=404, detail="Not Found")

    if not FRONTEND_DIST.exists():
        raise HTTPException(status_code=404, detail="Not Found")

    dist_root = FRONTEND_DIST.resolve()
    requested = (FRONTEND_DIST / full_path).resolve()
    if dist_root not in requested.parents and requested != dist_root:
        raise HTTPException(status_code=404, detail="Not Found")

    if requested.is_dir():
        requested = requested / "index.html"

    if requested.exists() and requested.is_file():
        return FileResponse(requested)

    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
