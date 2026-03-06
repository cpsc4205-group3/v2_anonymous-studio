# Export Functionality

## Overview

The export functionality allows compliance officers to download audit logs and pipeline history in both CSV and JSON formats for documentation and audit purposes.

## Features

### Audit Log Export

Export audit logs with applied filters to track all compliance-related actions.

**Supported Formats:**
- **CSV**: Spreadsheet-friendly format for Excel/Google Sheets
- **JSON**: Structured format for programmatic processing

**Location:** Audit page (`/audit`)

**Buttons:**
- "Export CSV" - Downloads filtered audit logs as CSV
- "Export JSON" - Downloads filtered audit logs as JSON

**Filename Format:**
- CSV: `audit_log_YYYYMMDD_HHMMSS.csv`
- JSON: `audit_log_YYYYMMDD_HHMMSS.json`

**CSV Columns:**
- Time
- Actor
- Action
- Resource
- Details
- Severity

**Features:**
- Respects current filter settings (search text, severity)
- Includes all visible audit entries
- Logs export action to audit trail
- Shows success notification with entry count

### Pipeline Data Export

Export pipeline cards (all or filtered) with complete metadata.

**Supported Formats:**
- **CSV**: Spreadsheet-friendly format
- **JSON**: Full metadata with attestation signatures

**Location:** Pipeline page (`/pipeline`)

**Buttons:**
- "Export All CSV" - Downloads all pipeline cards as CSV
- "Export All JSON" - Downloads all pipeline cards with full metadata as JSON

**Filename Format:**
- CSV: `pipeline_cards_YYYYMMDD_HHMMSS.csv`
- JSON: `pipeline_cards_YYYYMMDD_HHMMSS.json`

**CSV Columns:**
- ID
- Title
- Description
- Status
- Priority
- Card Type
- Assignee
- Labels
- Data Source
- Session ID
- Scenario ID
- Job Status
- Attested
- Attested By
- Attested At
- Attestation
- Created At
- Updated At

**JSON Fields (Complete Metadata):**
All CSV columns plus:
- `attestation_sig_alg` - Signature algorithm (e.g., "Ed25519")
- `attestation_sig_key_id` - Signer key identifier
- `attestation_sig` - Base64 detached signature
- `attestation_sig_public_key` - Base64 Ed25519 public key
- `attestation_sig_payload` - Canonical payload JSON
- `attestation_sig_payload_hash` - SHA-256 hex of payload
- `attestation_sig_verified` - Boolean verification status
- `attestation_sig_error` - Error message if signature failed

**Features:**
- Includes all card metadata
- Resolves job status from Taipy Core
- Logs export action to audit trail
- Shows success notification with card count

## Security Considerations

### Data Sanitization
- All exports use pandas `to_csv()` and `json.dumps()` - no pickle serialization
- CSV properly escapes special characters
- JSON uses `default=str` for safe datetime serialization

### Input Validation
- Empty data checks prevent errors
- Exception handling catches and logs all export failures
- No user-provided filenames (prevents path traversal)

### Audit Trail
All export actions are logged with:
- Actor: "user"
- Action: "audit.export" or "pipeline.export"
- Resource: "audit/all" or "pipeline/all"
- Details: Entry/card count and format

## Usage Examples

### Export Filtered Audit Logs

1. Navigate to `/audit`
2. Apply filters (search text, severity level)
3. Click "Apply" to filter the table
4. Click "Export CSV" or "Export JSON"
5. File downloads automatically with timestamp

### Export All Pipeline Cards

1. Navigate to `/pipeline`
2. Scroll to "Export Pipeline Data" section
3. Click "Export All CSV" for spreadsheet format
4. Click "Export All JSON" for complete metadata

### Export Specific Status Cards

Currently exports all cards. Future enhancement: status filtering via `on_pipeline_export_filtered_csv()`.

## API Reference

### Audit Export Functions

#### `on_audit_export_csv(state)`
Exports current filtered audit table to CSV.

**Parameters:**
- `state`: Taipy GUI state object

**Returns:** None (triggers download via `taipy.gui.download()`)

**Notifications:**
- Warning: No audit entries to export
- Success: Exported N entries
- Error: Export failed

#### `on_audit_export_json(state)`
Exports current filtered audit table to JSON.

**Parameters:**
- `state`: Taipy GUI state object

**Returns:** None (triggers download)

**JSON Structure:**
```json
[
  {
    "Time": "12:00:00",
    "Actor": "user1",
    "Action": "card.create",
    "Resource": "card/abc123",
    "Details": "Created new card",
    "Severity": "info"
  }
]
```

### Pipeline Export Functions

#### `on_pipeline_export_csv(state)`
Exports all pipeline cards to CSV.

**Parameters:**
- `state`: Taipy GUI state object

**Returns:** None (triggers download)

**Notifications:**
- Warning: No pipeline cards to export
- Success: Exported N cards
- Error: Export failed

#### `on_pipeline_export_json(state)`
Exports all pipeline cards to JSON with full metadata.

**Parameters:**
- `state`: Taipy GUI state object

**Returns:** None (triggers download)

**JSON Structure:**
```json
[
  {
    "id": "card-123",
    "title": "Data Processing Task",
    "description": "Process customer data",
    "status": "in_progress",
    "priority": "high",
    "card_type": "file",
    "assignee": "user1",
    "labels": ["urgent", "pii"],
    "data_source": "customer_db",
    "session_id": "session-456",
    "scenario_id": "scenario-789",
    "job_status": "running",
    "attested": true,
    "attested_by": "compliance_officer",
    "attested_at": "2024-03-06T14:30:00",
    "attestation": "Verified compliance",
    "attestation_sig_alg": "Ed25519",
    "attestation_sig_verified": true,
    "created_at": "2024-03-05T10:00:00",
    "updated_at": "2024-03-06T14:30:00"
  }
]
```

#### `on_pipeline_export_filtered_csv(state)`
Exports pipeline cards filtered by status (future enhancement).

**Parameters:**
- `state`: Taipy GUI state object (reads `state.pipeline_export_status_filter`)

**Returns:** None (triggers download)

**Status Filters:**
- `"backlog"` - Cards in backlog
- `"in_progress"` - Cards in progress
- `"review"` - Cards under review
- `"done"` - Completed cards
- `"all"` - All cards (default)

## Testing

### Test Coverage
13 test cases covering:
- CSV/JSON export with data
- Empty data handling
- Datetime serialization
- Large datasets (500-1000 records)
- Exception handling
- Security (no pickle, data sanitization)
- All metadata fields present

### Running Tests
```bash
pytest tests/test_export_functionality.py -v
```

### Test Results
- ✅ All 13 tests passing
- ✅ Large dataset support verified
- ✅ Security checks pass
- ✅ Exception handling verified

## Future Enhancements

1. **Status-based filtering** - Enable `on_pipeline_export_filtered_csv()` with UI selector
2. **Date range filtering** - Export audit logs for specific time periods
3. **Excel format** - Native `.xlsx` export with formatting
4. **Scheduled exports** - Automated daily/weekly exports
5. **Email delivery** - Send exports to compliance team
6. **Custom columns** - User-selectable fields for export
7. **Batch export** - Export multiple resources at once

## Troubleshooting

### Export Button Not Visible
- Ensure you're on the correct page (`/audit` or `/pipeline`)
- Scroll to the export section (below tables)

### "No entries/cards to export" Warning
- Add data first (create cards, perform actions)
- Check that filters aren't excluding all data

### Export Failed Error
- Check logs for detailed error message
- Verify store backend is accessible
- Ensure sufficient disk space for temp files

### Downloaded File Is Empty
- Verify data exists before export
- Check browser download settings
- Try alternative format (CSV vs JSON)

## Related Documentation

- [Store API](store-utils.md) - Data access utilities
- [Audit Trail](../README.md#audit-log) - Audit system overview
- [Pipeline Management](../README.md#pipeline) - Kanban board usage
- [Compliance Features](../README.md#compliance) - Attestation and signing
