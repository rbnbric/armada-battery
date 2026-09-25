"""Same-origin web gateway for the Armada Battery task vertical slice."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from battery.task_slice import AdapterError, engine_from_environment
from battery.scenarios import run_scenarios


ROOT = Path(__file__).parent
app = FastAPI(title="Armada Battery", version="0.1.0", docs_url="/api/docs")
engine = engine_from_environment()


class PrepareRequest(BaseModel):
    task_definition_reviewed: bool = False


class WebAppRequest(BaseModel):
    name: str
    namespace: str
    dispatch_class: str
    resource: str = ""


class GrantRoleRequest(BaseModel):
    username: str
    role_name: str
    role_reviewed: bool = False


class ScheduleRequest(BaseModel):
    period: str
    start_time: str = ""
    every: str = "1"
    day: str = ""


def current_operator() -> str:
    return str(engine.adapter.get_info().get("username") or "unknown")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/static/app.css")
def css():
    return FileResponse(ROOT / "static" / "app.css", media_type="text/css")


@app.get("/static/app.js")
def javascript():
    return FileResponse(ROOT / "static" / "app.js", media_type="text/javascript")


@app.get("/api/state")
def state():
    try:
        return engine.dashboard()
    except AdapterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/catalog")
def catalog():
    try:
        return engine.admin_catalog()
    except AdapterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/observations")
def observations():
    return engine.observations()


@app.get("/api/assurance")
def assurance():
    if not engine.adapter.synthetic:
        return {
            "scope": "live",
            "available": False,
            "detail": "Synthetic assurance does not establish live IRIS behavior.",
        }
    return {"scope": "synthetic", "available": True, **run_scenarios()}


@app.get("/api/evidence")
def evidence(limit: int = 20):
    return engine.audit_trail(limit)


@app.post("/api/intents/task/{task_id}/run")
def prepare_task_run(task_id: int, request: PrepareRequest):
    try:
        return engine.prepare_task_run(
            task_id,
            requested_by=current_operator(),
            task_definition_reviewed=request.task_definition_reviewed,
        )
    except AdapterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/actions/task-run/{certificate}/execute")
def execute_task_run(
    certificate: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    try:
        return engine.execute_task_run(certificate, idempotency_key)
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/intents/web-app/create")
def prepare_web_app(request: WebAppRequest):
    try:
        return engine.prepare_create_web_app(
            name=request.name,
            namespace=request.namespace,
            dispatch_class=request.dispatch_class,
            resource=request.resource,
            requested_by=current_operator(),
        )
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/intents/access/grant-role")
def prepare_role_grant(request: GrantRoleRequest):
    try:
        return engine.prepare_grant_role(
            username=request.username,
            role_name=request.role_name,
            requested_by=current_operator(),
            role_reviewed=request.role_reviewed,
        )
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/intents/task/{task_id}/schedule")
def prepare_task_schedule(task_id: int, request: ScheduleRequest):
    try:
        return engine.prepare_schedule_task(
            task_id=task_id,
            period=request.period,
            start_time=request.start_time,
            every=request.every,
            day=request.day,
            requested_by=current_operator(),
        )
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/actions/admin/{certificate}/execute")
def execute_admin(
    certificate: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    try:
        return engine.execute_admin(certificate, idempotency_key)
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/receipts/{receipt_id}/reconcile")
def reconcile(receipt_id: str):
    try:
        return engine.reconcile(receipt_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receipt not found") from exc
    except AdapterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/health")
def health():
    return {"ok": True, "ledger_valid": engine.ledger.verify()}
