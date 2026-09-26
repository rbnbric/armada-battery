"""Same-origin web gateway for the Armada Battery task vertical slice."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import os
import hmac
import hashlib
import time
import secrets
from urllib.parse import urlsplit
from pydantic import BaseModel

from battery.task_slice import AdapterError, engine_from_environment
from battery.scenarios import run_scenarios
from battery.ledger import sanitize


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
    return os.environ.get("BATTERY_OPERATOR_NAME", "local-operator")


class LoginRequest(BaseModel):
    access_key: str


def access_key():
    return os.environ.get("BATTERY_ACCESS_KEY", "")


def session_signature(expires):
    return hmac.new(access_key().encode(), expires.encode(), hashlib.sha256).hexdigest()


def authenticated(request):
    if not access_key():
        return True  # Explicit single-operator localhost mode, documented below.
    token = request.cookies.get("battery_session", "")
    try:
        expiry, signature = token.split(".", 1)
        return int(expiry) > time.time() and hmac.compare_digest(
            signature, session_signature(expiry)
        )
    except (ValueError, TypeError):
        return False


@app.post("/api/session")
def login(body: LoginRequest):
    if not access_key() or not secrets.compare_digest(body.access_key, access_key()):
        raise HTTPException(401, "Access key was not accepted")
    expires = str(int(time.time()) + 3600)
    response = JSONResponse({"operator": current_operator()})
    response.set_cookie(
        "battery_session",
        expires + "." + session_signature(expires),
        httponly=True,
        samesite="strict",
        max_age=3600,
        secure=os.environ.get("BATTERY_SECURE_COOKIE") == "true",
    )
    return response


@app.middleware("http")
async def access_boundary(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse(
                {"detail": "Cross-origin changes are not accepted"}, status_code=403
            )
    if (
        request.url.path.startswith("/api/")
        and request.url.path not in {"/api/health", "/api/session"}
        and not authenticated(request)
    ):
        return JSONResponse({"detail": "Operator sign-in required"}, status_code=401)
    return await call_next(request)


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
        return {
            **engine.dashboard(),
            "operator": current_operator(),
            "access_mode": "authenticated single operator"
            if access_key()
            else "local single operator",
            "instance": urlsplit(
                getattr(engine.adapter, "base_url", "http://synthetic")
            ).hostname,
        }
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=sanitize(str(exc))) from exc


@app.get("/api/catalog")
def catalog():
    try:
        return engine.admin_catalog()
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=sanitize(str(exc))) from exc


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
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=sanitize(str(exc))) from exc


@app.post("/api/actions/task-run/{certificate}/execute")
def execute_task_run(
    certificate: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    try:
        return engine.execute_task_run(
            certificate, idempotency_key, operator=current_operator()
        )
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=sanitize(str(exc))) from exc


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
        raise HTTPException(status_code=409, detail=sanitize(str(exc))) from exc


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
        raise HTTPException(status_code=409, detail=sanitize(str(exc))) from exc


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
        raise HTTPException(status_code=409, detail=sanitize(str(exc))) from exc


@app.post("/api/actions/admin/{certificate}/execute")
def execute_admin(
    certificate: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    try:
        return engine.execute_admin(
            certificate, idempotency_key, operator=current_operator()
        )
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=sanitize(str(exc))) from exc


@app.post("/api/receipts/{receipt_id}/reconcile")
def reconcile(receipt_id: str):
    try:
        return engine.reconcile(receipt_id, operator=current_operator())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receipt not found") from exc
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=sanitize(str(exc))) from exc


@app.get("/api/tasks/{task_id}")
def task_detail(task_id: int):
    try:
        return {
            "task": sanitize(engine.adapter.get_task(task_id)),
            "captured_at": engine.now().isoformat(),
        }
    except AdapterError as exc:
        raise HTTPException(502, sanitize(str(exc))) from exc


@app.get("/api/receipts/{receipt_id}")
def receipt_detail(receipt_id: str):
    with engine.ledger.locked():
        try:
            receipt = engine.get_receipt(receipt_id, operator=current_operator())
        except KeyError as exc:
            raise HTTPException(404, "Receipt unavailable for this operator") from exc
        ids = set(receipt["before_evidence"] + receipt["after_evidence"])
        evidence = [
            r["payload"]
            for r in engine.ledger.records
            if r["event_type"] == "observation" and r["payload"].get("id") in ids
        ]
        records = [
            {
                "sequence": r["sequence"],
                "digest": r["digest"],
                "event_type": r["event_type"],
                "recorded_at": r["recorded_at"],
            }
            for r in engine.ledger.records
            if r["payload"].get("id") == receipt_id
        ]
        return sanitize({"receipt": receipt, "evidence": evidence, "ledger": records})


@app.get("/api/receipts")
def receipts(execution_key: str | None = None):
    return {
        "receipts": engine.list_receipts(
            operator=current_operator(), execution_key=execution_key
        )
    }


@app.get("/api/health")
def health():
    try:
        with engine.ledger.locked():
            valid = engine.ledger.verify()
    except (ValueError, OSError, KeyError):
        valid = False
    return JSONResponse(
        {
            "ok": valid,
            "ledger_valid": valid,
            "scope": "local event store; IRIS connectivity is not established by this check",
        },
        status_code=200 if valid else 503,
    )
