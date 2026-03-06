"""
Anonymous Studio — Store Data Access Utilities
===============================================
Provides reusable helper functions for filtering, querying, and aggregating
store data. These utilities reduce code duplication in app.py and provide
consistent interfaces for common data access patterns.

Usage in app.py:

    from store.utils import (
        filter_audit_entries,
        filter_appointments_by_status,
        count_by_severity,
        count_by_priority,
        filter_sessions_by_time_window,
    )
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from store.models import PIISession, PipelineCard, Appointment, AuditEntry


# ── Time Window Utilities ─────────────────────────────────────────────────────

def parse_time_window(window: str) -> Optional[datetime]:
    """Convert time window string to cutoff datetime.
    
    Args:
        window: One of "today", "week", "month", "all"
    
    Returns:
        datetime cutoff, or None for "all"
    """
    now = datetime.now()
    if window == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif window == "week":
        return now - timedelta(days=7)
    elif window == "month":
        return now - timedelta(days=30)
    return None  # "all"


def is_in_time_window(timestamp_str: str, window: str) -> bool:
    """Check if ISO timestamp string is within the given time window.
    
    Args:
        timestamp_str: ISO format timestamp string
        window: One of "today", "week", "month", "all"
    
    Returns:
        True if timestamp is within window (always True for "all")
    """
    cutoff = parse_time_window(window)
    if cutoff is None:
        return True
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return ts >= cutoff
    except (ValueError, AttributeError):
        return False


# ── Audit Log Filtering ───────────────────────────────────────────────────────

def filter_audit_entries(
    entries: List[AuditEntry],
    severity: Optional[str] = None,
    search_text: Optional[str] = None,
    time_window: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> List[AuditEntry]:
    """Filter audit entries by multiple criteria.
    
    Args:
        entries: List of audit entries to filter
        severity: Filter by severity level (e.g., "info", "warning", "critical")
                  Pass "all" or None to include all severities
        search_text: Case-insensitive search in action and details fields
        time_window: Filter by time window ("today", "week", "month", "all")
        resource_type: Filter by resource type (e.g., "pipeline", "session")
        resource_id: Filter by specific resource ID
    
    Returns:
        Filtered list of audit entries
    """
    result = []
    search_lower = search_text.lower() if search_text else None
    
    for entry in entries:
        # Severity filter
        if severity and severity != "all" and entry.severity != severity:
            continue
        
        # Search text filter
        if search_lower:
            if (search_lower not in entry.action.lower() and 
                search_lower not in entry.details.lower()):
                continue
        
        # Time window filter
        if time_window:
            if not is_in_time_window(entry.timestamp, time_window):
                continue
        
        # Resource type filter
        if resource_type and entry.resource_type != resource_type:
            continue
        
        # Resource ID filter
        if resource_id and entry.resource_id != resource_id:
            continue
        
        result.append(entry)
    
    return result


def count_by_severity(entries: List[AuditEntry]) -> Dict[str, int]:
    """Count audit entries by severity level.
    
    Args:
        entries: List of audit entries
    
    Returns:
        Dict mapping severity level to count
    """
    counts = {"info": 0, "warning": 0, "critical": 0}
    for entry in entries:
        severity = str(getattr(entry, "severity", "info")).lower()
        if severity in counts:
            counts[severity] += 1
    return counts


# ── Appointment Filtering ──────────────────────────────────────────────────────

def filter_appointments_by_status(
    appointments: List[Appointment],
    status: Optional[str] = None,
) -> List[Appointment]:
    """Filter appointments by status.
    
    Args:
        appointments: List of appointments
        status: Filter by status ("scheduled", "completed", "cancelled")
                Pass None to include all
    
    Returns:
        Filtered list of appointments
    """
    if not status or status == "all":
        return appointments
    return [a for a in appointments if a.status == status]


def filter_appointments_by_time_range(
    appointments: List[Appointment],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Appointment]:
    """Filter appointments by date range.
    
    Args:
        appointments: List of appointments
        start_date: ISO format start date (inclusive), or None for no start limit
        end_date: ISO format end date (inclusive), or None for no end limit
    
    Returns:
        Filtered list of appointments
    """
    result = []
    for appt in appointments:
        if not appt.scheduled_for:
            continue
        
        if start_date and appt.scheduled_for < start_date:
            continue
        
        if end_date and appt.scheduled_for > end_date:
            continue
        
        result.append(appt)
    
    return result


def get_scheduled_appointments(
    appointments: List[Appointment],
) -> List[Appointment]:
    """Get only scheduled (not completed/cancelled) appointments.
    
    Args:
        appointments: List of appointments
    
    Returns:
        List of scheduled appointments
    """
    return [a for a in appointments if a.status == "scheduled"]


# ── Card Filtering ─────────────────────────────────────────────────────────────

def filter_cards_by_priority(
    cards: List[PipelineCard],
    priority: Optional[str] = None,
) -> List[PipelineCard]:
    """Filter cards by priority level.
    
    Args:
        cards: List of pipeline cards
        priority: Filter by priority ("low", "medium", "high", "critical")
                  Pass None to include all
    
    Returns:
        Filtered list of cards
    """
    if not priority or priority == "all":
        return cards
    return [c for c in cards if c.priority == priority]


def count_by_priority(cards: List[PipelineCard]) -> Dict[str, int]:
    """Count cards by priority level.
    
    Args:
        cards: List of pipeline cards
    
    Returns:
        Dict mapping priority level to count
    """
    counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for card in cards:
        priority = str(getattr(card, "priority", "medium")).lower()
        if priority in counts:
            counts[priority] += 1
    return counts


def filter_cards_by_status(
    cards: List[PipelineCard],
    status: Optional[str] = None,
) -> List[PipelineCard]:
    """Filter cards by pipeline status.
    
    Args:
        cards: List of pipeline cards
        status: Filter by status ("backlog", "in_progress", "review", "done")
                Pass None to include all
    
    Returns:
        Filtered list of cards
    """
    if not status or status == "all":
        return cards
    return [c for c in cards if c.status == status]


def filter_cards_attested(cards: List[PipelineCard]) -> List[PipelineCard]:
    """Get only attested cards.
    
    Args:
        cards: List of pipeline cards
    
    Returns:
        List of attested cards
    """
    return [c for c in cards if c.attested]


# ── Session Filtering ──────────────────────────────────────────────────────────

def filter_sessions_by_time_window(
    sessions: List[PIISession],
    time_window: str,
) -> List[PIISession]:
    """Filter sessions by time window.
    
    Args:
        sessions: List of PII sessions
        time_window: One of "today", "week", "month", "all"
    
    Returns:
        Filtered list of sessions
    """
    return [s for s in sessions if is_in_time_window(s.created_at, time_window)]


def filter_sessions_by_entities(
    sessions: List[PIISession],
    entity_types: List[str],
) -> List[PIISession]:
    """Filter sessions that detected any of the given entity types.
    
    Args:
        sessions: List of PII sessions
        entity_types: List of entity type strings (e.g., ["PERSON", "EMAIL_ADDRESS"])
    
    Returns:
        Filtered list of sessions
    """
    if not entity_types:
        return sessions
    
    result = []
    for session in sessions:
        if not session.entity_counts:
            continue
        
        # Check if any of the target entity types were detected
        detected_types = set(session.entity_counts.keys()) if isinstance(session.entity_counts, dict) else set()
        if any(entity_type in detected_types for entity_type in entity_types):
            result.append(session)
    
    return result


def count_sessions_by_operator(sessions: List[PIISession]) -> Dict[str, int]:
    """Count sessions by anonymization operator used.
    
    Args:
        sessions: List of PII sessions
    
    Returns:
        Dict mapping operator name to count
    """
    counts: Dict[str, int] = {}
    for session in sessions:
        operator = session.operator or "replace"
        counts[operator] = counts.get(operator, 0) + 1
    return counts


# ── Generic Filtering Utilities ────────────────────────────────────────────────

def filter_by_predicate(
    items: List[Any],
    predicate: Callable[[Any], bool],
) -> List[Any]:
    """Generic filter using a predicate function.
    
    Args:
        items: List of items to filter
        predicate: Function that returns True for items to keep
    
    Returns:
        Filtered list
    """
    return [item for item in items if predicate(item)]


def group_by(
    items: List[Any],
    key_func: Callable[[Any], str],
) -> Dict[str, List[Any]]:
    """Group items by a key function.
    
    Args:
        items: List of items to group
        key_func: Function that extracts the grouping key from each item
    
    Returns:
        Dict mapping key to list of items
    """
    groups: Dict[str, List[Any]] = {}
    for item in items:
        key = key_func(item)
        if key not in groups:
            groups[key] = []
        groups[key].append(item)
    return groups


def count_by(
    items: List[Any],
    key_func: Callable[[Any], str],
) -> Dict[str, int]:
    """Count items grouped by a key function.
    
    Args:
        items: List of items to count
        key_func: Function that extracts the grouping key from each item
    
    Returns:
        Dict mapping key to count
    """
    counts: Dict[str, int] = {}
    for item in items:
        key = key_func(item)
        counts[key] = counts.get(key, 0) + 1
    return counts
