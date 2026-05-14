from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import Base, engine, get_db
from .ir.graph_patch import namespace_graph_patch_ids
from .ir.services import expand_slot as expand_slot_service
from .ir.services import initialize_workspace_from_idea
from .ir.exporter import export_markdown
from .ir.impact import compute_impact_preview
from .ir.projections import build_projection
from .ir.rewrite import rewrite_workspace

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

@asynccontextmanager
async def lifespan(_: FastAPI):
    if load_dotenv:
        load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

    Base.metadata.create_all(bind=engine)
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
    ir = initialize_workspace_from_idea(req.prompt)
    ws = crud.upsert_workspace_from_ir(db, ir)
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.get("/api/workspaces/default")
def get_default_workspace(db: Session = Depends(get_db)):
    ws = db.query(models.Workspace).order_by(models.Workspace.updated_at.desc()).first()
    if not ws:
        raise HTTPException(status_code=404, detail="当前没有 workspace，请先通过 /workspaces/bootstrap 创建")
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


@app.patch("/api/workspaces/{workspace_id}/issues/{issue_id}/details")
def patch_issue_details(workspace_id: str, issue_id: str, req: schemas.IssueUpdateRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.update_issue(db, ws, issue_id, req.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.patch("/api/workspaces/{workspace_id}/choices/{choice_id}")
def patch_choice(workspace_id: str, choice_id: str, req: schemas.ChoiceUpdateRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    crud.update_choice(db, ws, choice_id, req.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.post("/api/workspaces/{workspace_id}/issues/{issue_id}/slots")
def create_issue_slot(workspace_id: str, issue_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    slot_id = crud.create_slot_for_issue(db, ws, issue_id)
    db.commit()
    db.refresh(ws)
    return {"slotId": slot_id, "workspace": crud.serialize_workspace(ws)}


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
def diagnose(workspace_id: str, req: schemas.DiagnoseRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    result = crud.run_diagnosis(db, ws, req.scope)
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


@app.post("/api/workspaces/{workspace_id}/slots")
def create_slot(workspace_id: str, req: schemas.CreateSlotRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    slot_id = f"slot_{uuid.uuid4().hex[:10]}"
    payload = req.model_dump()
    payload["id"] = slot_id
    crud.apply_graph_patch(db, ws, {"addSlots": [payload]})
    db.commit()
    db.refresh(ws)
    return {"slotId": slot_id, "workspace": crud.serialize_workspace(ws)}


@app.patch("/api/workspaces/{workspace_id}/slots/{slot_id}")
def patch_slot(workspace_id: str, slot_id: str, req: schemas.SlotUpdateRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    patch = {"updateSlots": [{"id": slot_id, **req.model_dump(exclude_unset=True)}]}
    crud.apply_graph_patch(db, ws, patch)
    db.commit()
    db.refresh(ws)
    return crud.serialize_workspace(ws)


@app.post("/api/workspaces/{workspace_id}/slots/{slot_id}/expand")
def expand_slot(workspace_id: str, slot_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    cg_id = expand_slot_service(db, ws, slot_id)
    db.commit()
    db.refresh(ws)
    return {"choiceGroupId": cg_id, "workspace": crud.serialize_workspace(ws)}


@app.post("/api/workspaces/{workspace_id}/rewrite")
def rewrite(workspace_id: str, req: schemas.RewriteRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    result = rewrite_workspace(db, ws, req.scope, req.instruction)
    db.commit()
    db.refresh(ws)
    return {"result": result, "workspace": crud.serialize_workspace(ws)}


@app.post("/api/workspaces/{workspace_id}/impact-preview")
def impact_preview(workspace_id: str, req: schemas.ImpactPreviewRequest, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    patch = req.patch
    if not patch and req.choiceId:
        choice = db.get(models.Choice, req.choiceId)
        if not choice:
            raise HTTPException(status_code=404, detail=f"Choice `{req.choiceId}` 不存在")
        group = db.get(models.ChoiceGroup, choice.choice_group_id)
        if not group or group.workspace_id != ws.id:
            raise HTTPException(status_code=404, detail=f"Choice `{req.choiceId}` 不属于当前 workspace")
        patch = choice.patch or {}
    if not patch:
        raise HTTPException(status_code=400, detail="patch 或 choiceId 至少提供一个")
    patch = namespace_graph_patch_ids(ws.id, patch)
    preview = compute_impact_preview(db, ws, patch)
    return {"impactPreview": preview}


@app.get("/api/workspaces/{workspace_id}/projections/{projection_kind}")
def get_projection(workspace_id: str, projection_kind: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    ir = crud.serialize_workspace(ws)
    projection = build_projection(ir, projection_kind)
    return {"projectionKind": projection_kind, "projection": projection}

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


@app.get("/api/workspaces/{workspace_id}/export/json")
def export_workspace_json(workspace_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    return crud.serialize_workspace(ws)


@app.get("/api/workspaces/{workspace_id}/export/markdown")
def export_workspace_markdown(workspace_id: str, db: Session = Depends(get_db)):
    ws = crud.get_workspace_or_404(db, workspace_id)
    md = export_markdown(crud.serialize_workspace(ws))
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")

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
