# All Stories - Complete Inventory

This document consolidates ALL stories from the anonymous-studio project, including implemented features, work in progress, and backlog items. This was created to recover stories that may have been lost when the repository was archived.

**Last Updated:** 2026-03-06
**Total Stories:** 15 pipeline cards + additional feature requests documented below

---

## Story Status Legend

- ✅ **Done** — Fully implemented and tested
- ⚠️ **In Progress** — Partially implemented, work ongoing
- 📋 **Backlog** — Not yet started, planned for future
- 🔍 **Lost** — Referenced in memories but not found in codebase

---

## Pipeline Cards (card-001 through card-015)

These are the core project stories defined in `store/memory.py` as demo cards.

### ✅ card-001: Q1 Customer Export Anonymization
**Status:** Review (implemented)  
**Priority:** High  
**Labels:** HIPAA, customer-data  
**Assignee:** Carley Fant  
**Description:** De-identify customer names, emails, and SSNs from Q1 export.

### ✅ card-002: HR Records PII Scrub
**Status:** In Progress (implemented)  
**Priority:** Critical  
**Labels:** GDPR, HR  
**Assignee:** Sakshi Patel  
**Description:** Remove all PII from historical HR records prior to archival.

### ✅ card-003: Research Dataset Anonymization
**Status:** Done ✅  
**Priority:** Medium  
**Labels:** research  
**Assignee:** Diamond Hogans  
**Attestation:** ✅ Attested by Compliance Officer  
**Description:** Apply k-anonymity preprocessing and de-identify participant data.  
**Notes:** Verified: all PII removed per IRB protocol.

### 📋 card-004: Patient Records HIPAA Compliance
**Status:** Backlog  
**Priority:** High  
**Labels:** HIPAA, healthcare  
**Description:** Scrub PHI from inbound patient dataset before ML pipeline.

### 📋 card-005: Vendor Contract Data Review
**Status:** Backlog  
**Priority:** Low  
**Labels:** contracts  
**Assignee:** Elijah Jenkins  
**Description:** Flag and remove bank account numbers and SSNs from vendor contracts.

---

## Feature Enhancement Stories (card-006 through card-010)

### ✅ card-006: Allowlist / Denylist Support
**Status:** Done ✅  
**Priority:** Medium  
**Labels:** feature, pii-engine  
**Implementation:** `pii_engine.py`, `app.py`  
**Description:** Add allow_list and deny_list inputs to PII Text page. Pass allow_list= to analyzer.analyze() and use ad_hoc_recognizers=[PatternRecognizer(deny_list=...)] for denylist.

**Acceptance Criteria:**
- [x] UI fields for allowlist and denylist on PII Text page
- [x] PIIEngine.analyze() accepts allowlist parameter
- [x] PIIEngine.analyze() accepts denylist parameter
- [x] CUSTOM_DENYLIST entity type created
- [x] Post-filtering for allowlist implemented
- [x] Regex pattern cache for denylist

### ⚠️ card-007: Encrypt Operator Key Management
**Status:** In Progress (Partial) ⚠️  
**Priority:** Medium  
**Labels:** feature, security  
**Description:** Implement encrypt operator in pii_engine.py. Add 'encrypt' option to UI operator selector. Add UI field for AES encryption key (128/192/256-bit). Store key securely via env var (ANON_ENCRYPT_KEY). Enable DeanonymizeEngine decrypt round-trip for reversible anonymization.

**What's Implemented:**
- ✅ Presidio library supports encrypt/decrypt operators
- ✅ Backend infrastructure ready

**What's Missing:**
- ❌ UI operator selector doesn't include 'encrypt' option
- ❌ No UI field for encryption key input
- ❌ OperatorConfig("encrypt", {"key": key}) not implemented in pii_engine.py
- ❌ No env var (ANON_ENCRYPT_KEY) support
- ❌ No DeanonymizeEngine integration

**Acceptance Criteria:**
- [ ] Add 'encrypt' to operator selector dropdown
- [ ] Add encrypted text input field for AES key (128/192/256-bit)
- [ ] Validate key length (16/24/32 characters)
- [ ] Read ANON_ENCRYPT_KEY from environment
- [ ] Implement OperatorConfig("encrypt", {"key": key})
- [ ] Add DeanonymizeEngine.deanonymize() capability
- [ ] Test encrypt/decrypt round-trip
- [ ] Document key management in README

### ✅ card-008: ORGANIZATION Entity Support
**Status:** Done ✅  
**Priority:** Low  
**Labels:** feature, pii-engine  
**Implementation:** `pii_engine.py`  
**Description:** Add ORGANIZATION to ALL_ENTITIES in pii_engine.py. Configure ORG→ORGANIZATION NLP mapping with 0.4 confidence multiplier to reduce false positives.

**Acceptance Criteria:**
- [x] ORGANIZATION added to ALL_ENTITIES (now 17 entities total)
- [x] NLP mapping: spaCy ORG tag → ORGANIZATION
- [x] Confidence multiplier configured
- [x] Requires trained spaCy model (en_core_web_lg recommended)

### ✅ card-009: REST API for PII Detection
**Status:** Done ✅  
**Priority:** High  
**Labels:** feature, api  
**Implementation:** `rest_main.py`, `services/auth0_rest.py`  
**Description:** Build REST API endpoints for PII detection, de-identification, and pipeline CRUD using FastAPI. Add API key authentication and Swagger documentation.

**Acceptance Criteria:**
- [x] REST API entrypoint (rest_main.py)
- [x] Taipy Rest integration
- [x] Auth0 JWT authentication support
- [x] API endpoints for PII operations
- [x] Pipeline CRUD endpoints
- [x] Swagger/OpenAPI documentation

### ✅ card-010: MongoDB Persistence Layer
**Status:** Done ✅  
**Priority:** Critical  
**Labels:** feature, infrastructure  
**Assignee:** Sakshi Patel  
**Implementation:** `store/mongo.py`, `store/duckdb.py`  
**Description:** Implement MongoStore backend for persistent storage of sessions, cards, appointments, and audit logs. Read MONGODB_URI from env. Replace in-memory store for production use.

**Acceptance Criteria:**
- [x] MongoStore class in store/mongo.py
- [x] All StoreBase abstract methods implemented
- [x] MONGODB_URI environment variable support
- [x] Sessions, cards, appointments, audit logs persisted
- [x] Bonus: DuckDBStore alternative backend
- [x] Store backend switching via ANON_STORE_BACKEND env var

---

## Backlog Stories (card-011 through card-015)

### ✅ card-011: Export Audit Logs as CSV/JSON
**Status:** Done ✅  
**Priority:** Medium  
**Labels:** feature, compliance  
**Implementation:** `app.py` (callbacks), `pages/definitions.py` (UI buttons), `tests/test_export.py` (7 tests)  
**Description:** Add download buttons to export audit log and pipeline data in CSV and JSON formats for compliance documentation sharing.

**Acceptance Criteria:**
- [x] Add "Export CSV" button to Audit page
- [x] Add "Export JSON" button to Audit page
- [x] Add "Export All CSV" button to Pipeline page
- [x] Add "Export All JSON" button to Pipeline page
- [x] Implement on_audit_export_csv callback
- [x] Implement on_audit_export_json callback
- [x] Implement on_pipeline_export_csv callback
- [x] Implement on_pipeline_export_json callback
- [x] Use pandas.to_csv() for CSV export
- [x] Use json.dumps() for JSON export (no pickle)
- [x] All exports log to audit trail
- [x] Show success/error notifications
- [x] Use taipy.gui.download() for file download

### 📋 card-012: Image PII Detection via OCR
**Status:** Backlog 📋  
**Priority:** Low  
**Labels:** feature, ocr  
**Description:** Accept PNG/JPG uploads, extract text via Tesseract OCR, then apply Presidio PII detection to the extracted text. Display annotated results.

**Acceptance Criteria:**
- [ ] Add file upload widget for PNG/JPG on PII Text page
- [ ] Integrate Tesseract OCR (pytesseract library)
- [ ] Extract text from uploaded images
- [ ] Pass extracted text to PIIEngine.analyze()
- [ ] Display OCR text with PII highlighting
- [ ] Show detected entities table for image
- [ ] Add error handling for unsupported formats
- [ ] Document Tesseract installation in README

**Technical Requirements:**
- Install pytesseract: `pip install pytesseract`
- System dependency: Tesseract OCR binary
- Supported formats: PNG, JPG, JPEG
- Max file size: 10MB (configurable)

### 📋 card-013: Role-Based Authentication
**Status:** Backlog 📋  
**Priority:** High  
**Labels:** feature, security  
**Description:** Implement user login with email/password and role-based access (Admin, Compliance Officer, Developer, Researcher). Store hashed passwords in MongoDB.

**Acceptance Criteria:**
- [ ] User registration page with email/password
- [ ] Password hashing (bcrypt or argon2)
- [ ] Login page with authentication
- [ ] Session management
- [ ] Role assignment (Admin, Compliance Officer, Developer, Researcher)
- [ ] Role-based access control (RBAC)
- [ ] Protect sensitive pages based on role
- [ ] Store users collection in MongoDB
- [ ] Logout functionality
- [ ] Password reset flow (optional)

**Roles and Permissions:**
- **Admin:** Full access to all features, user management
- **Compliance Officer:** View/attest cards, export audit logs, view all data
- **Developer:** Create/edit pipeline cards, run jobs, view own data
- **Researcher:** Read-only access, can view anonymized outputs

### 📋 card-014: Compliance Review Notifications
**Status:** Backlog 📋  
**Priority:** Medium  
**Labels:** feature, compliance  
**Description:** Send email or in-app notifications 24 hours before scheduled review appointments. Include appointment details and linked pipeline card information.

**Acceptance Criteria:**
- [ ] Background notification service (daemon thread or scheduled job)
- [ ] Check appointments 24 hours in advance
- [ ] Send email notifications (SMTP integration)
- [ ] OR show in-app notifications (banner/toast)
- [ ] Notification includes: appointment title, time, description, linked card
- [ ] Mark notifications as sent (avoid duplicates)
- [ ] Configuration: SMTP settings in env vars
- [ ] Graceful failure if email service unavailable

**Technical Requirements:**
- Email backend: SMTP (smtplib) or SendGrid API
- Environment variables: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
- Notification scheduler: runs every hour
- Persistence: track notification_sent flag on appointments

**Integration with Existing Code:**
- Extends `scheduler.py` (appointment scheduler already exists)
- Use `store.list_appointments()` to find upcoming appointments
- Filter for appointments in 24-hour window
- Send notification and update appointment record

### 📋 card-015: File Attachments on Pipeline Cards
**Status:** Backlog 📋  
**Priority:** Medium  
**Labels:** feature, pipeline  
**Description:** Allow users to attach anonymized output files (CSV, TXT, JSON) to pipeline cards. Support multiple attachments per card with download capability.

**Acceptance Criteria:**
- [ ] Add "Attachments" section to pipeline card detail page
- [ ] File upload widget for attachments (multiple files)
- [ ] Support formats: CSV, TXT, JSON
- [ ] Store files: local filesystem or MongoDB GridFS
- [ ] Display attachment list on card (filename, size, upload date)
- [ ] Download button for each attachment
- [ ] Delete attachment capability
- [ ] Max file size limit (e.g., 50MB per file)
- [ ] Audit log: attachment.upload, attachment.delete events

**Technical Requirements:**
- Storage backend: filesystem (ANON_STORAGE path) or GridFS
- File metadata: store in PipelineCard.attachments (List[Dict])
- Each attachment: {filename, size, uploaded_at, stored_path, content_type}
- Download uses taipy.gui.download()

**Data Model Changes:**
```python
@dataclass
class PipelineCard:
    # ... existing fields ...
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    # Each dict: {"filename": str, "size": int, "uploaded_at": str, 
    #             "stored_path": str, "content_type": str}
```

---

## Additional Notes

### Export Functionality (card-011) — Recovered

Export functionality was previously reported as lost but has been **re-implemented and verified**:

- `app.py:5140-5157` — `on_audit_export_csv()` exports audit log to CSV
- `app.py:5160-5176` — `on_audit_export_json()` exports audit log to JSON
- `app.py:5179-5196` — `on_pipeline_export_csv()` exports pipeline cards to CSV
- `app.py:5199-5215` — `on_pipeline_export_json()` exports pipeline cards to JSON
- `pages/definitions.py:503-504` — Pipeline export buttons
- `pages/definitions.py:604-605` — Audit export buttons
- `tests/test_export.py` — 7 tests

---

## Summary Statistics

**Total Pipeline Cards:** 15
- ✅ Done: 7 (card-001, card-002, card-003, card-006, card-008, card-009, card-010, card-011)
- ⚠️ In Progress: 1 (card-007)
- 📋 Backlog: 4 (card-004, card-005, card-012, card-013, card-014, card-015)

**Priority Breakdown:**
- Critical: 2 (2 done)
- High: 3 (1 done, 2 backlog)
- Medium: 7 (4 done, 1 in progress, 2 backlog)
- Low: 3 (1 done, 2 backlog)

**Feature Categories:**
- Core PII Detection: 7 done
- Infrastructure: 1 done
- Security: 1 in progress, 1 backlog
- Compliance: 1 backlog
- User Experience: 2 backlog

---

## Implementation Recommendations

### Immediate Priority (Next Sprint)
1. **card-007:** Complete encrypt operator (finish what's started)
2. **card-013:** Role-based authentication (high security priority)

### Medium Priority (Sprint +1)
3. **card-014:** Compliance notifications (extends existing scheduler)
4. **card-015:** File attachments on cards (enhances workflow)
5. **card-004:** Patient records HIPAA (high priority use case)

### Low Priority (Future)
7. **card-012:** Image OCR (new capability)
8. **card-005:** Vendor contracts (low priority use case)

---

## Related Documentation

- **Feature Parity Tracking:** `docs/feature-parity.md`
- **Demo Cards Source:** `store/memory.py` lines 269-415
- **Store Interface:** `store/base.py`
- **Pipeline UI:** `pages/definitions.py`
- **App Callbacks:** `app.py`

---

## How to Use This Document

### For Project Managers
- Review backlog priorities
- Assign stories to sprints
- Track implementation status
- Update card statuses in `store/memory.py` when done

### For Developers
- Pick a backlog story to implement
- Follow acceptance criteria
- Update feature-parity.md when complete
- Change card status from "backlog" to "done"
- Add tests in `tests/` directory
- Document any new env vars in README

### For Compliance/Security
- Review high-priority security stories (card-007, card-013)
- Verify attestation requirements met (card-003 example)
- Ensure audit logging for all features (card-011, card-014)

---

---

**Document Maintenance:**
- Update this file when implementing backlog stories
- Mark stories as done when completed
- Add new stories to appropriate section
- Keep priority/status current
- Cross-reference with feature-parity.md

**Version History:**
- v1.0 (2026-03-06): Initial comprehensive inventory, identified lost export functionality
