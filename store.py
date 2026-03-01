"""
Anonymous Studio - Data Store
In-memory store that mirrors the MongoDB schema from the project spec.
Swap out for real pymongo by changing the backend class.
"""

from __future__ import annotations
import json
import uuid
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict


# ─── Helper ───────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _uid() -> str:
    return str(uuid.uuid4())[:8]


# ─── Domain Models ────────────────────────────────────────────────────────────

@dataclass
class PIISession:
    """Stores one de-identification run."""
    id: str = field(default_factory=_uid)
    title: str = "Untitled Session"
    original_text: str = ""
    anonymized_text: str = ""
    entities: List[Dict] = field(default_factory=list)
    entity_counts: Dict[str, int] = field(default_factory=dict)
    operator: str = "replace"
    source_type: str = "text"   # "text" | "file"
    file_name: Optional[str] = None
    created_at: str = field(default_factory=_now)
    pipeline_card_id: Optional[str] = None


@dataclass
class PipelineCard:
    """Kanban card for a data pipeline task."""
    id: str = field(default_factory=_uid)
    title: str = "New Task"
    description: str = ""
    status: str = "backlog"   # backlog | in_progress | review | done
    assignee: str = ""
    priority: str = "medium"  # low | medium | high | critical
    labels: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    attestation: str = ""     # compliance attestation note
    attested: bool = False
    attested_by: str = ""
    attested_at: Optional[str] = None
    scenario_id: Optional[str] = None  # taipy.core Scenario id
    job_id: Optional[str] = None       # anonymization job id


@dataclass
class Appointment:
    """Scheduled review / compliance meeting."""
    id: str = field(default_factory=_uid)
    title: str = "PII Review"
    description: str = ""
    scheduled_for: str = ""   # ISO datetime
    duration_mins: int = 30
    attendees: List[str] = field(default_factory=list)
    pipeline_card_id: Optional[str] = None
    status: str = "scheduled"  # scheduled | completed | cancelled
    created_at: str = field(default_factory=_now)


@dataclass
class AuditEntry:
    """Immutable audit log entry."""
    id: str = field(default_factory=_uid)
    timestamp: str = field(default_factory=_now)
    actor: str = "system"
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    details: str = ""
    severity: str = "info"    # info | warning | critical


# ─── In-Memory Store ──────────────────────────────────────────────────────────

class DataStore:
    def __init__(self):
        self._sessions: Dict[str, PIISession] = {}
        self._cards: Dict[str, PipelineCard] = {}
        self._appointments: Dict[str, Appointment] = {}
        self._audit: List[AuditEntry] = []
        self._seed_demo_data()

    # ── Sessions ──────────────────────────────────────────────────────────────

    def add_session(self, session: PIISession) -> PIISession:
        self._sessions[session.id] = session
        self._log("system", "pii.anonymize", "session", session.id,
                  f"Anonymized {len(session.entities)} entities using '{session.operator}'")
        return session

    def get_session(self, session_id: str) -> Optional[PIISession]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[PIISession]:
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    # ── Pipeline Cards ─────────────────────────────────────────────────────────

    def add_card(self, card: PipelineCard) -> PipelineCard:
        self._cards[card.id] = card
        self._log("system", "pipeline.create", "card", card.id,
                  f"Created card '{card.title}' in '{card.status}'")
        return card

    def update_card(self, card_id: str, **kwargs) -> Optional[PipelineCard]:
        card = self._cards.get(card_id)
        if not card:
            return None
        old_status = card.status
        for k, v in kwargs.items():
            if hasattr(card, k):
                setattr(card, k, v)
        card.updated_at = _now()
        if "status" in kwargs and kwargs["status"] != old_status:
            self._log("system", "pipeline.move", "card", card_id,
                      f"Moved '{card.title}' from '{old_status}' → '{kwargs['status']}'")
        if kwargs.get("attested"):
            self._log("system", "compliance.attest", "card", card_id,
                      f"Attested by '{card.attested_by}'", severity="info")
        return card

    def delete_card(self, card_id: str) -> bool:
        if card_id in self._cards:
            title = self._cards[card_id].title
            del self._cards[card_id]
            self._log("system", "pipeline.delete", "card", card_id, f"Deleted '{title}'", "warning")
            return True
        return False

    def get_card(self, card_id: str) -> Optional[PipelineCard]:
        return self._cards.get(card_id)

    def list_cards(self, status: Optional[str] = None) -> List[PipelineCard]:
        cards = list(self._cards.values())
        if status:
            cards = [c for c in cards if c.status == status]
        return sorted(cards, key=lambda c: c.updated_at, reverse=True)

    def cards_by_status(self) -> Dict[str, List[PipelineCard]]:
        result = {"backlog": [], "in_progress": [], "review": [], "done": []}
        for card in self._cards.values():
            result.setdefault(card.status, []).append(card)
        return result

    # ── Appointments ───────────────────────────────────────────────────────────

    def add_appointment(self, appt: Appointment) -> Appointment:
        self._appointments[appt.id] = appt
        self._log("system", "schedule.create", "appointment", appt.id,
                  f"Scheduled '{appt.title}' for {appt.scheduled_for}")
        return appt

    def update_appointment(self, appt_id: str, **kwargs) -> Optional[Appointment]:
        appt = self._appointments.get(appt_id)
        if not appt:
            return None
        for k, v in kwargs.items():
            if hasattr(appt, k):
                setattr(appt, k, v)
        return appt

    def delete_appointment(self, appt_id: str) -> bool:
        if appt_id in self._appointments:
            del self._appointments[appt_id]
            return True
        return False

    def list_appointments(self) -> List[Appointment]:
        return sorted(
            self._appointments.values(),
            key=lambda a: a.scheduled_for,
        )

    def upcoming_appointments(self, limit: int = 5) -> List[Appointment]:
        now = _now()
        upcoming = [a for a in self._appointments.values()
                    if a.scheduled_for >= now and a.status == "scheduled"]
        return sorted(upcoming, key=lambda a: a.scheduled_for)[:limit]

    # ── Audit Log ──────────────────────────────────────────────────────────────

    def _log(self, actor: str, action: str, resource_type: str,
             resource_id: str, details: str = "", severity: str = "info"):
        entry = AuditEntry(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            severity=severity,
        )
        self._audit.append(entry)

    def list_audit(self, limit: int = 200) -> List[AuditEntry]:
        return list(reversed(self._audit[-limit:]))

    def log_user_action(self, actor: str, action: str, resource_type: str,
                        resource_id: str, details: str = "", severity: str = "info"):
        self._log(actor, action, resource_type, resource_id, details, severity)

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        sessions = list(self._sessions.values())
        all_entities: List[str] = []
        for s in sessions:
            for etype, cnt in s.entity_counts.items():
                all_entities.extend([etype] * cnt)

        entity_freq: Dict[str, int] = {}
        for e in all_entities:
            entity_freq[e] = entity_freq.get(e, 0) + 1

        cards = list(self._cards.values())
        return {
            "total_sessions": len(sessions),
            "total_entities_redacted": len(all_entities),
            "entity_breakdown": entity_freq,
            "pipeline_by_status": {
                s: len([c for c in cards if c.status == s])
                for s in ["backlog", "in_progress", "review", "done"]
            },
            "total_appointments": len(self._appointments),
            "total_audit_entries": len(self._audit),
            "attested_cards": len([c for c in cards if c.attested]),
        }

    # ── Seed Demo Data ─────────────────────────────────────────────────────────

    def _seed_demo_data(self):
        # Demo pipeline cards
        demo_cards = [
            PipelineCard(
                id="card-001", title="Q1 Customer Export Anonymization",
                description="De-identify customer names, emails, and SSNs from Q1 export before sharing with analytics team.",
                status="review", assignee="Carley Fant", priority="high",
                labels=["HIPAA", "customer-data"], attested=False,
            ),
            PipelineCard(
                id="card-002", title="HR Records PII Scrub",
                description="Remove all PII from historical HR records prior to archival.",
                status="in_progress", assignee="Sakshi Patel", priority="critical",
                labels=["GDPR", "HR"], attested=False,
            ),
            PipelineCard(
                id="card-003", title="Research Dataset Anonymization",
                description="Apply k-anonymity preprocessing and de-identify participant data.",
                status="done", assignee="Diamond Hogans", priority="medium",
                labels=["research"], attested=True, attested_by="Compliance Officer",
                attested_at=_now(),
                attestation="Verified: all PII removed per IRB protocol.",
            ),
            PipelineCard(
                id="card-004", title="Patient Records HIPAA Compliance",
                description="Scrub PHI from inbound patient dataset before ML pipeline ingestion.",
                status="backlog", assignee="", priority="high",
                labels=["HIPAA", "healthcare"],
            ),
            PipelineCard(
                id="card-005", title="Vendor Contract Data Review",
                description="Flag and remove bank account numbers and SSNs from vendor contracts.",
                status="backlog", assignee="Elijah Jenkins", priority="low",
                labels=["contracts"],
            ),
        ]
        for card in demo_cards:
            self._cards[card.id] = card

        # Demo appointments
        demo_appts = [
            Appointment(
                id="appt-001", title="Q1 Export Compliance Review",
                description="Review de-identified Q1 dataset with compliance team.",
                scheduled_for="2026-03-05T10:00:00",
                duration_mins=60,
                attendees=["Carley Fant", "Compliance Officer", "Data Analyst"],
                pipeline_card_id="card-001",
                status="scheduled",
            ),
            Appointment(
                id="appt-002", title="HR Anonymization Sign-off",
                description="Final attestation meeting for HR records.",
                scheduled_for="2026-03-10T14:00:00",
                duration_mins=30,
                attendees=["Sakshi Patel", "HR Lead"],
                pipeline_card_id="card-002",
                status="scheduled",
            ),
            Appointment(
                id="appt-003", title="Research IRB Attestation",
                description="Post-completion IRB attestation review.",
                scheduled_for="2026-02-20T09:00:00",
                duration_mins=45,
                attendees=["Diamond Hogans", "IRB Committee"],
                pipeline_card_id="card-003",
                status="completed",
            ),
        ]
        for appt in demo_appts:
            self._appointments[appt.id] = appt

        # Seed some audit entries
        self._log("system", "app.start", "system", "app", "Anonymous Studio initialized")
        self._log("carley.fant", "pii.anonymize", "session", "demo-1",
                  "Anonymized 12 entities (EMAIL×3, PHONE×2, SSN×7)")
        self._log("sakshi.patel", "pipeline.move", "card", "card-002",
                  "Moved 'HR Records PII Scrub' from backlog → in_progress")
        self._log("diamond.hogans", "compliance.attest", "card", "card-003",
                  "Attested research dataset, severity=info")


# ── Global singleton ───────────────────────────────────────────────────────────
_store: Optional[DataStore] = None

def get_store() -> DataStore:
    global _store
    if _store is None:
        _store = DataStore()
    return _store