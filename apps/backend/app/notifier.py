"""SLA breach notifications: webhook dispatch + email stub + in-app notification feed.

A background scheduler (APScheduler) scans cases for SLA breaches every 5 minutes.
Admins configure webhook_urls in `notification_settings`.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("onetouch.notifier")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def get_settings(db) -> Dict[str, Any]:
    doc = await db.notification_settings.find_one({"id": "singleton"}, {"_id": 0})
    if not doc:
        doc = {
            "id": "singleton",
            "webhook_urls": [],
            "email_recipients": [],
            "enabled": True,
            "sla_breach_severity_threshold": "high",  # high+critical trigger alerts
            "daily_brief_enabled": True,
            "daily_brief_hour_utc": 8,
            "updated_at": _iso(datetime.now(timezone.utc)),
        }
        await db.notification_settings.insert_one(dict(doc))
    # Backfill new fields on existing singletons
    changed = False
    for k, default in [("daily_brief_enabled", True), ("daily_brief_hour_utc", 8)]:
        if k not in doc:
            doc[k] = default; changed = True
    if changed:
        await db.notification_settings.update_one({"id": "singleton"}, {"$set": doc})
    return doc


async def save_settings(db, patch: Dict[str, Any]) -> Dict[str, Any]:
    patch["updated_at"] = _iso(datetime.now(timezone.utc))
    await db.notification_settings.update_one({"id": "singleton"}, {"$set": patch}, upsert=True)
    return await get_settings(db)


async def _dispatch_webhook(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send payload to webhook. Slack URLs get Block-Kit reformatting."""
    try:
        if "hooks.slack.com" in url:
            payload = _to_slack_block_kit(payload)
        async with httpx.AsyncClient(timeout=6.0) as c:
            r = await c.post(url, json=payload)
            return {"url": url, "status_code": r.status_code, "ok": 200 <= r.status_code < 300}
    except Exception as e:
        return {"url": url, "error": str(e), "ok": False}


def _to_slack_block_kit(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a standard notification payload into Slack Block-Kit format."""
    etype = payload.get("event_type", "event")
    sev = (payload.get("severity") or "info").lower()
    emoji = {"critical": ":rotating_light:", "high": ":warning:", "medium": ":large_yellow_circle:", "low": ":white_circle:", "info": ":information_source:"}.get(sev, ":bell:")
    color = {"critical": "#FF3B30", "high": "#FF9F0A", "medium": "#FFD60A", "low": "#30D158", "info": "#0A84FF"}.get(sev, "#0A84FF")

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} OneTouch Audit · {etype}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{payload.get('title','')}*"}},
    ]
    body = payload.get("body", "")
    if body:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body}})

    # Daily brief: include top_risks rendering if present
    extras = payload.get("extras") or {}
    if extras.get("kpis"):
        kpis = extras["kpis"]
        fields = [
            {"type": "mrkdwn", "text": f"*Readiness*\n{kpis.get('audit_readiness_pct', 0):.1f}%"},
            {"type": "mrkdwn", "text": f"*Exposure*\n${kpis.get('unresolved_high_risk_exposure', 0):,.0f}"},
            {"type": "mrkdwn", "text": f"*Open cases*\n{kpis.get('open_cases', 0)}"},
            {"type": "mrkdwn", "text": f"*SLA*\n{kpis.get('remediation_sla_pct', 0):.1f}%"},
        ]
        blocks.append({"type": "section", "fields": fields})
    if extras.get("top_risks"):
        lines = []
        for i, r in enumerate(extras["top_risks"][:3], start=1):
            lines.append(f"{i}. *{r.get('control_code','')}* · {r.get('entity','')} · ${r.get('financial_exposure', 0):,.0f} — {r.get('title','')[:90]}")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Top 3 risks*\n" + "\n".join(lines)}})

    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": f"_OneTouch Audit AI · {payload.get('timestamp','')}_"}
    ]})

    return {
        "text": f"{emoji} {payload.get('title','')}",
        "attachments": [{"color": color, "blocks": blocks}],
    }


async def notify(db, *, event_type: str, title: str, body: str, severity: str,
                 target_id: str, target_type: str, extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    settings = await get_settings(db)
    notif_id = str(uuid.uuid4())
    now = _iso(datetime.now(timezone.utc))
    notif = {
        "id": notif_id,
        "event_type": event_type,
        "title": title,
        "body": body,
        "severity": severity,
        "target_id": target_id,
        "target_type": target_type,
        "created_at": now,
        "dispatched_to": [],
        "email_stub_logged": False,
        "extras": extras or {},
    }

    if settings.get("enabled"):
        payload = {
            "event_type": event_type, "title": title, "body": body,
            "severity": severity, "target_id": target_id, "target_type": target_type,
            "timestamp": now, "source": "OneTouchAuditAI",
            "extras": extras or {},
        }
        for url in settings.get("webhook_urls", []):
            result = await _dispatch_webhook(url, payload)
            notif["dispatched_to"].append(result)
        # Email stub: log only (wire Resend/SendGrid later)
        if settings.get("email_recipients"):
            logger.info(f"EMAIL STUB → {settings['email_recipients']} · {title}")
            notif["email_stub_logged"] = True

    await db.notifications.insert_one(dict(notif))
    return notif


async def scan_sla_breaches(db) -> Dict[str, Any]:
    """Scan cases for SLA breaches; emit notifications only once per case per day."""
    settings = await get_settings(db)
    if not settings.get("enabled"):
        return {"scanned": 0, "notified": 0, "skipped": "disabled"}

    threshold = settings.get("sla_breach_severity_threshold", "high")
    sev_whitelist = {"critical": ["critical"], "high": ["critical", "high"], "medium": ["critical", "high", "medium"]}.get(threshold, ["critical", "high"])

    now = datetime.now(timezone.utc)
    notified = 0
    scanned = 0
    async for case in db.cases.find({"status": {"$ne": "closed"}, "severity": {"$in": sev_whitelist}}, {"_id": 0}):
        scanned += 1
        try:
            due = datetime.fromisoformat(case["due_date"])
        except Exception:
            continue
        if due >= now:
            continue
        # Already notified today?
        today = now.strftime("%Y-%m-%d")
        existing = await db.notifications.find_one({
            "target_id": case["id"], "event_type": "sla_breach",
            "created_at": {"$regex": f"^{today}"},
        })
        if existing:
            continue
        overdue_days = (now - due).days
        await notify(
            db,
            event_type="sla_breach",
            title=f"SLA breach · {case['control_code']} · {overdue_days}d overdue",
            body=f"Case '{case['title']}' ({case['severity']}) owned by {case['owner_email']} "
                 f"is {overdue_days} day(s) past SLA. Exposure ${case['financial_exposure']:,.2f}.",
            severity=case["severity"],
            target_id=case["id"],
            target_type="case",
        )
        notified += 1
    return {"scanned": scanned, "notified": notified}


async def list_notifications(db, limit: int = 50) -> List[Dict[str, Any]]:
    return [n async for n in db.notifications.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)]


async def send_daily_brief(db) -> Dict[str, Any]:
    """Compile daily CFO brief and dispatch to configured webhooks (Slack-formatted if applicable)."""
    # Lazy import to avoid circular dependency
    from .analytics import cfo_cockpit

    settings = await get_settings(db)
    if not settings.get("enabled"):
        return {"skipped": "disabled"}
    if not settings.get("daily_brief_enabled"):
        return {"skipped": "daily_brief_disabled"}

    data = await cfo_cockpit(db)
    k = data["kpis"]
    top_risks = data.get("top_risks", [])[:3]

    title = f"Daily CFO brief · Readiness {k['audit_readiness_pct']:.1f}% · ${k['unresolved_high_risk_exposure']:,.0f} exposure"
    body = (
        f"*{k['high_critical_open_cases']}* high/critical open cases · SLA {k['remediation_sla_pct']:.1f}% · "
        f"Evidence completeness {k['evidence_completeness_pct']:.1f}%"
    )
    extras = {
        "kpis": k,
        "top_risks": top_risks,
    }

    notif = await notify(
        db,
        event_type="daily_cfo_brief",
        title=title,
        body=body,
        severity="info",
        target_id="cfo_cockpit",
        target_type="dashboard",
        extras=extras,
    )
    return notif
