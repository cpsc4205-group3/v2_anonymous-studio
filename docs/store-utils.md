# Store Data Access Utilities

This document provides examples of how to use the data access utilities in `store/utils.py`.

## Overview

The `store.utils` module provides reusable helper functions for filtering, querying, and aggregating store data. All utilities are exported from the `store` package for easy import:

```python
from store import (
    filter_audit_entries,
    filter_appointments_by_status,
    filter_cards_by_priority,
    filter_sessions_by_time_window,
    count_by_severity,
    count_by_priority,
)
```

## Audit Log Filtering

### Filter by multiple criteria

```python
from store import get_store, filter_audit_entries

store = get_store()
audit_entries = store.list_audit(limit=1000)

# Filter by severity
warnings = filter_audit_entries(audit_entries, severity="warning")

# Filter by search text
pipeline_events = filter_audit_entries(audit_entries, search_text="pipeline")

# Filter by time window
recent = filter_audit_entries(audit_entries, time_window="week")

# Combine multiple filters
critical_recent_pipeline = filter_audit_entries(
    audit_entries,
    severity="critical",
    time_window="today",
    resource_type="pipeline"
)
```

### Count by severity

```python
from store import get_store, count_by_severity

store = get_store()
audit_entries = store.list_audit()
counts = count_by_severity(audit_entries)
# Returns: {"info": 150, "warning": 20, "critical": 2}
```

## Appointment Filtering

### Filter appointments by status or time range

```python
from store import get_store, filter_appointments_by_status, get_scheduled_appointments

store = get_store()
all_appointments = store.list_appointments()

# Only scheduled appointments
scheduled = filter_appointments_by_status(all_appointments, "scheduled")

# Or use convenience function
scheduled = get_scheduled_appointments(all_appointments)

# Filter by date range
from store import filter_appointments_by_time_range
from datetime import datetime, timedelta

start = datetime.now().isoformat()
end = (datetime.now() + timedelta(days=7)).isoformat()
upcoming = filter_appointments_by_time_range(all_appointments, start_date=start, end_date=end)
```

## Pipeline Card Filtering

### Filter cards by priority, status, or attestation

```python
from store import get_store, filter_cards_by_priority, filter_cards_attested

store = get_store()
all_cards = store.list_cards()

# High priority cards
high_priority = filter_cards_by_priority(all_cards, "high")

# Only attested cards
attested = filter_cards_attested(all_cards)

# Count cards by priority
from store import count_by_priority
priority_counts = count_by_priority(all_cards)
# Returns: {"low": 5, "medium": 10, "high": 3, "critical": 1}
```

## Session Filtering

### Filter sessions by time window or entity types

```python
from store import get_store, filter_sessions_by_time_window, filter_sessions_by_entities

store = get_store()
all_sessions = store.list_sessions()

# Sessions from the last week
recent_sessions = filter_sessions_by_time_window(all_sessions, "week")

# Sessions that detected PERSON or EMAIL_ADDRESS entities
person_email_sessions = filter_sessions_by_entities(
    all_sessions,
    ["PERSON", "EMAIL_ADDRESS"]
)

# Count sessions by operator
from store import count_sessions_by_operator
operator_counts = count_sessions_by_operator(all_sessions)
# Returns: {"replace": 45, "redact": 12, "mask": 8, "hash": 3}
```

## Generic Utilities

### Use generic filtering and grouping

```python
from store import filter_by_predicate, group_by, count_by

# Filter with custom predicate
high_value_cards = filter_by_predicate(
    all_cards,
    lambda c: c.priority in ("high", "critical") and not c.attested
)

# Group by custom key
cards_by_assignee = group_by(all_cards, lambda c: c.assignee or "unassigned")
# Returns: {"alice": [...], "bob": [...], "unassigned": [...]}

# Count by custom key
status_counts = count_by(all_cards, lambda c: c.status)
# Returns: {"backlog": 12, "in_progress": 5, "review": 3, "done": 15}
```

## Time Window Helpers

The time window utilities support the following windows:
- `"today"` — since midnight today
- `"week"` — last 7 days
- `"month"` — last 30 days
- `"all"` — no filtering

```python
from store import is_in_time_window, parse_time_window

# Check if timestamp is in window
if is_in_time_window(session.created_at, "week"):
    # Process recent session
    pass

# Get cutoff datetime for a window
cutoff = parse_time_window("week")  # Returns datetime 7 days ago
```

## Replacing In-line Filtering in app.py

### Before (in-line filtering):

```python
# app.py
warnings = [e for e in store.list_audit() if e.severity == "warning"]
scheduled_appts = [a for a in store.list_appointments() if a.status == "scheduled"]
```

### After (using utilities):

```python
# app.py
from store import filter_audit_entries, get_scheduled_appointments

warnings = filter_audit_entries(store.list_audit(), severity="warning")
scheduled_appts = get_scheduled_appointments(store.list_appointments())
```

## Benefits

1. **Code reuse** — No need to rewrite filtering logic in multiple places
2. **Consistency** — All filtering uses the same interfaces and behavior
3. **Testability** — Utilities are independently tested (31 test cases)
4. **Maintainability** — Changes to filtering logic only need to be made once
5. **Type safety** — All functions have proper type hints for IDE support

## Testing

Run the utility tests:

```bash
pytest tests/test_store_utils.py -v
```

All 31 tests cover:
- Time window parsing and filtering
- Audit entry filtering (severity, search, time, resource)
- Appointment filtering (status, time range)
- Card filtering (priority, status, attestation)
- Session filtering (time, entities, operator)
- Generic utilities (predicate, group_by, count_by)
