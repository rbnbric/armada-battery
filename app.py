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
import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from pydantic import BaseModel

from battery.task_slice import AdapterError, engine_from_environment
from battery.scenarios import run_scenarios
from battery.ledger import sanitize
from battery.ship_native_cases import NativeCases
from battery import ship_operator_sessions as operators


ROOT = Path(__file__).parent
@asynccontextmanager
async def lifespan(app):
    if operators.configured():
        operators.registry()
    async def maintain():
        while True:
            try:
                # Read endpoint expires abandoned native leases; never submits work.
                await asyncio.to_thread(NativeCases(engine).request, "/cases")
            except (AdapterError, ValueError, OSError):
                logging.getLogger(__name__).error("Native lease maintenance failed; the next sweep will retry")
            await asyncio.sleep(30)
    task = asyncio.create_task(maintain()) if os.getenv("BATTERY_NATIVE_URL") else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Armada Battery", version="0.1.0", docs_url="/api/docs", lifespan=lifespan)
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


def current_engine():
    who = operators.identity.get()
    return operators.operator_engine(who['name'], engine_from_environment) if who else engine


def current_operator() -> str:
    who = operators.identity.get()
    if who:
        return who['name']
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
    if operators.configured():
        try:
            issued = operators.issue(body.access_key)
        except (ValueError, OSError):
            raise HTTPException(503, "Operator registry unavailable")
        if not issued:
            raise HTTPException(401, "Access key was not accepted")
        name, token = issued
    elif not access_key() or not secrets.compare_digest(body.access_key, access_key()):
        raise HTTPException(401, "Access key was not accepted")
    expires = str(int(time.time()) + 3600)
    response = JSONResponse({"operator": name if operators.configured() else current_operator()})
    response.set_cookie(
        "battery_session",
        token if operators.configured() else expires + "." + session_signature(expires),
        httponly=True,
        samesite="strict",
        max_age=3600,
        secure=os.environ.get("BATTERY_SECURE_COOKIE") == "true",
    )
    return response


@app.post("/api/session/logout")
def logout():
    response = JSONResponse({"signed_out": True})
    response.delete_cookie("battery_session", httponly=True, samesite="strict", secure=os.environ.get("BATTERY_SECURE_COOKIE") == "true")
    return response


@app.middleware("http")
async def access_boundary(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse(
                {"detail": "Cross-origin changes are not accepted"}, status_code=403
            )
    public = request.url.path in {"/api/health", "/api/session", "/api/session/logout"} or not request.url.path.startswith("/api/")
    callback = request.url.path.startswith("/api/native-evidence/")
    who = None
    if operators.configured() and not public and not callback:
        try:
            who = operators.resolve(request.cookies.get("battery_session", ""))
        except (ValueError, OSError):
            return JSONResponse({"detail": "Operator registry unavailable"}, status_code=503)
        if not who:
            return JSONResponse({"detail": "Operator sign-in required"}, status_code=401)
        if who['role'] == 'observer' and request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            return JSONResponse({"detail": "This identity has read-only access"}, status_code=403)
    elif not public and not callback and not authenticated(request):
        return JSONResponse({"detail": "Operator sign-in required"}, status_code=401)
    marker = operators.identity.set(who)
    try:
        return await call_next(request)
    finally:
        operators.identity.reset(marker)



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
            **current_engine().dashboard(),
            "operator": current_operator(),
            "role": (operators.identity.get() or {}).get("role", "operator"),
            "access_mode": "shared service; isolated operator ledger" if operators.configured() else ("authenticated single operator" if access_key() else "local single operator"),
            "instance": urlsplit(
                getattr(current_engine().adapter, "base_url", "http://synthetic")
            ).hostname,
        }
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=sanitize(str(exc))) from exc


@app.get("/api/catalog")
def catalog():
    try:
        return current_engine().admin_catalog()
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=sanitize(str(exc))) from exc


@app.get("/api/observations")
def observations():
    return current_engine().observations()


@app.get("/api/findings/demonstration")
def demonstration_finding():
    try:
        return current_engine().demonstration_finding()
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=sanitize(str(exc))) from exc


@app.get("/api/assurance")
def assurance():
    if not current_engine().adapter.synthetic:
        return {
            "scope": "live",
            "available": False,
            "detail": "Synthetic assurance does not establish live IRIS behavior.",
        }
    return {"scope": "synthetic", "available": True, **run_scenarios()}


@app.get("/api/evidence")
def evidence(limit: int = 20):
    return current_engine().audit_trail(limit)


@app.post("/api/intents/task/{task_id}/run")
def prepare_task_run(task_id: int, request: PrepareRequest):
    try:
        return current_engine().prepare_task_run(
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
        return current_engine().execute_task_run(
            certificate, idempotency_key, operator=current_operator()
        )
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=sanitize(str(exc))) from exc


@app.post("/api/intents/web-app/create")
def prepare_web_app(request: WebAppRequest):
    try:
        return current_engine().prepare_create_web_app(
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
        return current_engine().prepare_grant_role(
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
        return current_engine().prepare_schedule_task(
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
        return current_engine().execute_admin(
            certificate, idempotency_key, operator=current_operator()
        )
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=sanitize(str(exc))) from exc


@app.post("/api/receipts/{receipt_id}/reconcile")
def reconcile(receipt_id: str):
    try:
        return current_engine().reconcile(receipt_id, operator=current_operator())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receipt not found") from exc
    except (AdapterError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=sanitize(str(exc))) from exc


@app.get("/api/tasks/{task_id}")
def task_detail(task_id: int):
    try:
        return {
            "task": sanitize(current_engine().adapter.get_task(task_id)),
            "captured_at": current_engine().now().isoformat(),
        }
    except AdapterError as exc:
        raise HTTPException(502, sanitize(str(exc))) from exc


@app.get("/api/receipts/{receipt_id}")
def receipt_detail(receipt_id: str):
    with current_engine().ledger.locked():
        try:
            receipt = current_engine().get_receipt(receipt_id, operator=current_operator())
        except KeyError as exc:
            raise HTTPException(404, "Receipt unavailable for this operator") from exc
        ids = set(receipt["before_evidence"] + receipt["after_evidence"])
        evidence = [
            r["payload"]
            for r in current_engine().ledger.records
            if r["event_type"] == "observation" and r["payload"].get("id") in ids
        ]
        records = [
            {
                "sequence": r["sequence"],
                "digest": r["digest"],
                "event_type": r["event_type"],
                "recorded_at": r["recorded_at"],
            }
            for r in current_engine().ledger.records
            if r["payload"].get("id") == receipt_id
        ]
        return sanitize({"receipt": receipt, "evidence": evidence, "ledger": records})


@app.get("/api/receipts")
def receipts(execution_key: str | None = None):
    return {
        "receipts": current_engine().list_receipts(
            operator=current_operator(), execution_key=execution_key
        )
    }


@app.get("/api/health")
def health():
    if operators.configured():
        try:
            operators.registry()
            return {"ok": True, "scope": "operator configuration only; per-operator ledgers and IRIS not checked"}
        except (ValueError, OSError):
            return JSONResponse({"ok": False, "scope": "operator configuration unavailable"}, status_code=503)
    try:
        with current_engine().ledger.locked():
            valid = current_engine().ledger.verify()
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


class NativeCaseRequest(BaseModel):
    receipt_id: str
    parent_id: str = ""


def native_cases():
    return NativeCases(current_engine(), operator=current_operator())


@app.get("/api/cases")
def list_native_cases():
    try:
        return native_cases().list(current_operator())
    except (AdapterError, ValueError) as exc:
        raise HTTPException(getattr(exc, "http_status", None) or 502, str(exc)) from exc


@app.get("/api/cases/{case_id}")
def get_native_case(case_id: str):
    try:
        return native_cases().get(case_id, current_operator())
    except KeyError as exc:
        raise HTTPException(404, "Case not found") from exc
    except (AdapterError, ValueError) as exc:
        raise HTTPException(getattr(exc, "http_status", None) or 502, str(exc)) from exc


@app.post("/api/cases")
def submit_native_case(body: NativeCaseRequest, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    try:
        return native_cases().submit(body.receipt_id, idempotency_key, current_operator(), body.parent_id)
    except KeyError as exc:
        raise HTTPException(404, "Receipt not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except AdapterError as exc:
        raise HTTPException(getattr(exc, "http_status", None) or 502, str(exc)) from exc


@app.get("/api/native-evidence/{case_id}")
def native_evidence(case_id: str, phase: str, x_battery_adapter: str = Header(default=""), x_battery_operator: str = Header(default="")):
    expected = os.environ.get("BATTERY_ADAPTER_KEY", "")
    if len(expected) < 32 or not hmac.compare_digest(expected, x_battery_adapter):
        raise HTTPException(401, "Native adapter authentication required")
    try:
        if operators.configured():
            selected = operators.operator_engine(x_battery_operator, engine_from_environment)
            return NativeCases(selected, operator=x_battery_operator).evidence(case_id, phase)
        if x_battery_operator and x_battery_operator != current_operator():
            raise KeyError(case_id)
        return native_cases().evidence(case_id, phase)
    except KeyError as exc:
        raise HTTPException(404, "Case not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except AdapterError as exc:
        raise HTTPException(502, "Evidence source unavailable") from exc
