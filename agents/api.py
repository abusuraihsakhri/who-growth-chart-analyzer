"""FastAPI interface for growth measurements and legacy audit demo."""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from growth_chart import analyze_growth
from .base import AuditLogger, PHIGuard, SecurityException
from .models import SystemTaskPayload
from .supervisor import SystemSupervisor

_supervisor = None
WEB_ROOT = Path(__file__).resolve().parent.parent / "web"


def _get_supervisor():
    global _supervisor
    if _supervisor is None:
        _supervisor = SystemSupervisor(model_provider=os.getenv("MODEL_PROVIDER", "mock"))
    return _supervisor


app = FastAPI(title="WHO Growth Chart Analyzer", version="3.1.0",
              description="WHO 2006 age-based indicators; separate non-clinical audit demonstration")


class GrowthRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    age_months: float = Field(ge=0, le=60)
    sex: str = Field(pattern="^[MmFf]$")
    weight_kg: float = Field(gt=0, le=500)
    height_cm: float = Field(gt=0, le=250)
    head_cm: float | None = Field(default=None, gt=0, le=100)
    measurement: str = Field(default="auto", pattern="^(auto|length|height)$")


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


@app.get("/health")
def health():
    return {"status": "ok", "service": "who-growth-chart-analyzer", "version": "3.1.0"}


@app.get("/metrics")
def metrics():
    return {"dossiers_processed_total": len(_get_supervisor().dossier_registry),
            "audit_blocks_total": len(AuditLogger.get_trail()),
            "audit_integrity_verified": AuditLogger.verify_integrity()}


@app.post("/api/growth")
def api_growth(payload: GrowthRequest):
    try:
        return analyze_growth(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/audit")
def api_audit(payload: SystemTaskPayload):
    try:
        return _get_supervisor().process_task(payload).to_dict()
    except SecurityException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    try:
        return {"response": _get_supervisor().query_supervisory_chat(req.query)}
    except (SecurityException, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/audit/logs")
def api_audit_logs():
    return {"audit_trail": AuditLogger.get_trail(),
            "verified": AuditLogger.verify_integrity()}


# Served last so API routes retain priority. The static dashboard works
# independently on GitHub Pages, with no backend and no PHI transmission.
app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")
