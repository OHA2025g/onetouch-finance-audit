"""Wave 3 — Compliance / governance REST stubs (workflows land incrementally)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user

router = APIRouter(prefix="/compliance-depth", tags=["compliance-depth"])


@router.get("/rpt/register")
async def rpt_register(current=Depends(get_current_user)):
    return {"items": [], "note": "Related-party transaction register — seed rpt_register collection."}


@router.get("/legal/notices")
async def legal_notices(current=Depends(get_current_user)):
    return {"items": [], "note": "Legal notice workflow — attach to compliance reviews."}


@router.get("/doa/rules")
async def doa_rules(current=Depends(get_current_user)):
    return {"items": [], "note": "Delegation of authority matrix."}


@router.get("/sod/campaigns")
async def sod_campaigns(status: Optional[str] = Query(None), current=Depends(get_current_user)):
    return {"items": [], "status_filter": status, "note": "SoD certification campaigns."}


@router.get("/mdq/summary")
async def mdq_summary(current=Depends(get_current_user)):
    return {"open_findings": 0, "note": "Master data quality command center (Wave 3)."}
