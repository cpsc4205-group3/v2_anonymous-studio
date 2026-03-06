"""Tests for store.utils data access utilities."""
from datetime import datetime, timedelta

import pytest

from store.models import PIISession, PipelineCard, Appointment, AuditEntry, _now
from store.utils import (
    # Time utilities
    parse_time_window,
    is_in_time_window,
    # Audit filtering
    filter_audit_entries,
    count_by_severity,
    # Appointment filtering
    filter_appointments_by_status,
    filter_appointments_by_time_range,
    get_scheduled_appointments,
    # Card filtering
    filter_cards_by_priority,
    filter_cards_by_status,
    filter_cards_attested,
    count_by_priority,
    # Session filtering
    filter_sessions_by_time_window,
    filter_sessions_by_entities,
    count_sessions_by_operator,
    # Generic utilities
    filter_by_predicate,
    group_by,
    count_by,
)


# ── Time Window Tests ──────────────────────────────────────────────────────────

def test_parse_time_window_today():
    cutoff = parse_time_window("today")
    assert cutoff is not None
    assert cutoff.hour == 0
    assert cutoff.minute == 0
    assert cutoff.second == 0


def test_parse_time_window_week():
    cutoff = parse_time_window("week")
    assert cutoff is not None
    now = datetime.now()
    # Should be approximately 7 days ago
    delta = now - cutoff
    assert 6.5 < delta.days < 7.5


def test_parse_time_window_month():
    cutoff = parse_time_window("month")
    assert cutoff is not None
    now = datetime.now()
    # Should be approximately 30 days ago
    delta = now - cutoff
    assert 29.5 < delta.days < 30.5


def test_parse_time_window_all():
    cutoff = parse_time_window("all")
    assert cutoff is None


def test_is_in_time_window_all():
    # "all" should include everything
    assert is_in_time_window("2020-01-01T00:00:00", "all")
    assert is_in_time_window(_now(), "all")


def test_is_in_time_window_today():
    now_ts = _now()
    assert is_in_time_window(now_ts, "today")
    
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    assert not is_in_time_window(yesterday, "today")


def test_is_in_time_window_week():
    now_ts = _now()
    assert is_in_time_window(now_ts, "week")
    
    three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()
    assert is_in_time_window(three_days_ago, "week")
    
    ten_days_ago = (datetime.now() - timedelta(days=10)).isoformat()
    assert not is_in_time_window(ten_days_ago, "week")


# ── Audit Entry Filtering Tests ────────────────────────────────────────────────

@pytest.fixture
def audit_entries():
    """Sample audit entries for testing."""
    now = datetime.now()
    return [
        AuditEntry(
            timestamp=(now - timedelta(hours=1)).isoformat(),
            actor="user1",
            action="pipeline.create",
            resource_type="pipeline",
            resource_id="card-001",
            details="Created card",
            severity="info",
        ),
        AuditEntry(
            timestamp=(now - timedelta(days=2)).isoformat(),
            actor="user2",
            action="session.save",
            resource_type="session",
            resource_id="sess-001",
            details="Saved session",
            severity="warning",
        ),
        AuditEntry(
            timestamp=(now - timedelta(days=10)).isoformat(),
            actor="admin",
            action="pipeline.delete",
            resource_type="pipeline",
            resource_id="card-002",
            details="Deleted old card",
            severity="critical",
        ),
    ]


def test_filter_audit_by_severity(audit_entries):
    warnings = filter_audit_entries(audit_entries, severity="warning")
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"


def test_filter_audit_by_search_text(audit_entries):
    results = filter_audit_entries(audit_entries, search_text="create")
    assert len(results) == 1
    assert "create" in results[0].action.lower()


def test_filter_audit_by_time_window(audit_entries):
    today = filter_audit_entries(audit_entries, time_window="today")
    assert len(today) == 1
    
    week = filter_audit_entries(audit_entries, time_window="week")
    assert len(week) == 2


def test_filter_audit_by_resource_type(audit_entries):
    pipeline = filter_audit_entries(audit_entries, resource_type="pipeline")
    assert len(pipeline) == 2
    assert all(e.resource_type == "pipeline" for e in pipeline)


def test_filter_audit_by_resource_id(audit_entries):
    results = filter_audit_entries(audit_entries, resource_id="card-001")
    assert len(results) == 1
    assert results[0].resource_id == "card-001"


def test_filter_audit_multiple_criteria(audit_entries):
    # Severity AND resource type
    results = filter_audit_entries(
        audit_entries,
        severity="critical",
        resource_type="pipeline"
    )
    assert len(results) == 1
    assert results[0].severity == "critical"
    assert results[0].resource_type == "pipeline"


def test_count_by_severity(audit_entries):
    counts = count_by_severity(audit_entries)
    assert counts["info"] == 1
    assert counts["warning"] == 1
    assert counts["critical"] == 1


# ── Appointment Filtering Tests ────────────────────────────────────────────────

@pytest.fixture
def appointments():
    """Sample appointments for testing."""
    now = datetime.now()
    return [
        Appointment(
            id="appt-001",
            title="Review A",
            scheduled_for=(now + timedelta(days=1)).isoformat(),
            duration_mins=30,
            status="scheduled",
        ),
        Appointment(
            id="appt-002",
            title="Review B",
            scheduled_for=(now + timedelta(days=5)).isoformat(),
            duration_mins=45,
            status="scheduled",
        ),
        Appointment(
            id="appt-003",
            title="Review C",
            scheduled_for=(now - timedelta(days=1)).isoformat(),
            duration_mins=30,
            status="completed",
        ),
        Appointment(
            id="appt-004",
            title="Review D",
            scheduled_for=(now + timedelta(days=2)).isoformat(),
            duration_mins=60,
            status="cancelled",
        ),
    ]


def test_filter_appointments_by_status(appointments):
    scheduled = filter_appointments_by_status(appointments, "scheduled")
    assert len(scheduled) == 2
    assert all(a.status == "scheduled" for a in scheduled)
    
    completed = filter_appointments_by_status(appointments, "completed")
    assert len(completed) == 1


def test_filter_appointments_by_status_all(appointments):
    all_appts = filter_appointments_by_status(appointments, None)
    assert len(all_appts) == 4


def test_filter_appointments_by_time_range(appointments):
    now = datetime.now()
    start = now.isoformat()
    end = (now + timedelta(days=3)).isoformat()
    
    future = filter_appointments_by_time_range(appointments, start_date=start)
    assert len(future) >= 2
    
    in_range = filter_appointments_by_time_range(
        appointments,
        start_date=start,
        end_date=end
    )
    assert len(in_range) >= 2


def test_get_scheduled_appointments(appointments):
    scheduled = get_scheduled_appointments(appointments)
    assert len(scheduled) == 2
    assert all(a.status == "scheduled" for a in scheduled)


# ── Card Filtering Tests ───────────────────────────────────────────────────────

@pytest.fixture
def cards():
    """Sample pipeline cards for testing."""
    return [
        PipelineCard(
            id="card-001",
            title="Card A",
            status="backlog",
            priority="high",
            attested=False,
        ),
        PipelineCard(
            id="card-002",
            title="Card B",
            status="in_progress",
            priority="critical",
            attested=False,
        ),
        PipelineCard(
            id="card-003",
            title="Card C",
            status="review",
            priority="medium",
            attested=True,
        ),
        PipelineCard(
            id="card-004",
            title="Card D",
            status="done",
            priority="low",
            attested=True,
        ),
    ]


def test_filter_cards_by_priority(cards):
    high = filter_cards_by_priority(cards, "high")
    assert len(high) == 1
    assert high[0].priority == "high"
    
    critical = filter_cards_by_priority(cards, "critical")
    assert len(critical) == 1


def test_filter_cards_by_priority_all(cards):
    all_cards = filter_cards_by_priority(cards, None)
    assert len(all_cards) == 4


def test_filter_cards_by_status(cards):
    backlog = filter_cards_by_status(cards, "backlog")
    assert len(backlog) == 1
    assert backlog[0].status == "backlog"


def test_filter_cards_attested(cards):
    attested = filter_cards_attested(cards)
    assert len(attested) == 2
    assert all(c.attested for c in attested)


def test_count_by_priority(cards):
    counts = count_by_priority(cards)
    assert counts["low"] == 1
    assert counts["medium"] == 1
    assert counts["high"] == 1
    assert counts["critical"] == 1


# ── Session Filtering Tests ────────────────────────────────────────────────────

@pytest.fixture
def sessions():
    """Sample PII sessions for testing."""
    now = datetime.now()
    return [
        PIISession(
            id="sess-001",
            title="Session A",
            created_at=(now - timedelta(hours=2)).isoformat(),
            operator="replace",
            entity_counts={"PERSON": 5, "EMAIL_ADDRESS": 2},
        ),
        PIISession(
            id="sess-002",
            title="Session B",
            created_at=(now - timedelta(days=5)).isoformat(),
            operator="redact",
            entity_counts={"PHONE_NUMBER": 3},
        ),
        PIISession(
            id="sess-003",
            title="Session C",
            created_at=(now - timedelta(days=15)).isoformat(),
            operator="replace",
            entity_counts={"PERSON": 10, "LOCATION": 4},
        ),
    ]


def test_filter_sessions_by_time_window(sessions):
    today = filter_sessions_by_time_window(sessions, "today")
    assert len(today) == 1
    
    week = filter_sessions_by_time_window(sessions, "week")
    assert len(week) == 2
    
    all_sessions = filter_sessions_by_time_window(sessions, "all")
    assert len(all_sessions) == 3


def test_filter_sessions_by_entities(sessions):
    # Find sessions that detected PERSON
    person = filter_sessions_by_entities(sessions, ["PERSON"])
    assert len(person) == 2
    
    # Find sessions that detected PHONE_NUMBER
    phone = filter_sessions_by_entities(sessions, ["PHONE_NUMBER"])
    assert len(phone) == 1
    
    # Multiple entity types (OR logic)
    multiple = filter_sessions_by_entities(sessions, ["PERSON", "PHONE_NUMBER"])
    assert len(multiple) == 3


def test_filter_sessions_by_entities_empty():
    sessions_list = [
        PIISession(
            id="sess-empty",
            title="Empty",
            created_at=_now(),
            operator="replace",
            entity_counts={},
        ),
    ]
    results = filter_sessions_by_entities(sessions_list, ["PERSON"])
    assert len(results) == 0


def test_count_sessions_by_operator(sessions):
    counts = count_sessions_by_operator(sessions)
    assert counts["replace"] == 2
    assert counts["redact"] == 1


# ── Generic Utilities Tests ────────────────────────────────────────────────────

def test_filter_by_predicate():
    items = [1, 2, 3, 4, 5, 6]
    evens = filter_by_predicate(items, lambda x: x % 2 == 0)
    assert evens == [2, 4, 6]


def test_group_by():
    items = ["apple", "banana", "apricot", "blueberry", "avocado"]
    grouped = group_by(items, lambda x: x[0])
    assert len(grouped["a"]) == 3
    assert len(grouped["b"]) == 2


def test_count_by():
    items = ["apple", "banana", "apricot", "blueberry", "avocado"]
    counts = count_by(items, lambda x: x[0])
    assert counts["a"] == 3
    assert counts["b"] == 2


def test_count_by_with_objects(cards):
    counts = count_by(cards, lambda c: c.status)
    assert counts["backlog"] == 1
    assert counts["in_progress"] == 1
    assert counts["review"] == 1
    assert counts["done"] == 1
