# Sprint 2 Retrospective

**Team Name:** Group 3 - Anonymous Studio

**Sprint Number:** 2

**Date Range:** 2/23/26 - 3/6/26

**Team Members:** Carley Fant, Diamond Hogans, Sakshi Patel, Elijah Jenkins

---

## Sprint Summary

This sprint focused on expanding Anonymous Studio beyond core PII detection into a full pipeline management workflow. The team aimed to implement entity type selection, detection rationale visibility, pipeline card creation, de-identification session traceability, MongoDB integration, data access utilities, and CSV/JSON audit log export. Five of seven planned user stories were completed. Detection rationale is functionally implemented but awaiting final review, and audit log export remains in the backlog. As in Sprint 1, the workload was carried by a subset of the team, with GitHub Copilot handling the majority of technical commits. Improving human contribution distribution remains the team's most critical improvement area heading into Sprint 3.

---

## GitHub Project Board Review

### Board View

![Sprint 2 Project Board - Board View](../images/sprint2-board-view.png)

### Table View

![Sprint 2 Project Board - Table View](../images/sprint2-table-view.png)

| Metric | Count |
|--------|-------|
| Tasks Planned at Sprint Start | 7 |
| Tasks Completed | 5 |
| Tasks In Review | 1 |
| Tasks Not Completed | 1 |

### Completed Tasks:
- **Issue #29** - Select PII entity types: Users can now filter detection to specific entity categories (names, emails, SSNs, etc.) via a multiselect panel
- **Issue #19** - Create new pipeline card: Users can create pipeline cards with card type and data source metadata
- **Issue #20** - Attach de-identification session: Sessions are auto-attached to pipeline cards on job completion, with duplicate prevention and bidirectional linking
- **Issue #66** - Provision MongoDB database: MongoDB integration configured for cloud/local deployment
- **Issue #68** - Implement data access utilities: Data access layer added to the store package with CRUD support and deserialization fixes

### In Review:
- **Issue #27** - View detection rationale: Detection rationale column and session loading implemented (PRs #16, #59 merged); issue remains open pending final acceptance

### Not Completed:
- **Issue #49** - Export audit logs as CSV/JSON: Implementation PR (#73) is open but not merged; moved back to backlog

### Scope Changes:
Several infrastructure and migration tasks were added during the sprint:
- Issue migration from archived v1 repo to active v2 repo
- GitHub Copilot SWE agent integration for development assistance
- DuckDB `done_at` handling fix for task completion transitions
- Secret scanning alert fix (credential-pattern placeholders in `.env.example`)
- Dependabot dependency updates (7 automated PRs)

These were necessary to stabilize the v2 repository after the Taipy refactor. Going forward, infrastructure work should be tracked as explicit sprint tasks rather than absorbed as unplanned scope.

---

## Sprint Planning vs. Reality

### Planned vs. Completed Work

Five of seven planned user stories were completed. The sprint delivered its core Kanban and traceability features but did not finish audit log export. Detection rationale is functionally present in the codebase but the acceptance criteria for Issue #27 have not been fully verified.

### Revised Sprint Planning vs. Reality

The sprint's technical scope was appropriate for a 4-person team. However, the execution pattern from Sprint 1 repeated: a small subset of contributors carried the workload. Additionally, GitHub Copilot (the SWE agent) authored the majority of merged commits, which raises questions about genuine team skill-building and individual accountability. Sprint 2 also saw a pattern of issues being created and closed on the same day (the final day of the sprint), which suggests retroactive issue tracking rather than active sprint management throughout the sprint.

### Contribution Distribution

Based on the GitHub contributor data for Sprint 2 (2/23/26 - 3/6/26):

- Copilot (GitHub SWE Agent): 20 commits
- Carley Fant: 4 commits
- Dependabot: 7 commits (automated)
- Diamond Hogans: 0 commits
- Sakshi Patel: 0 commits
- Elijah Jenkins: 0 commits

**Three out of four human team members have not made any code contributions in Sprint 2.** This is a continuation of the Sprint 1 pattern. The Sprint 1 action item requiring each team member to open at least 1 merged PR per week was not met by any team member other than Carley.

### Task Scoping

The sprint's seven user stories were appropriately sized for a 4-person team. The issue was not scope — it was participation.

---

## What Went Well

1. **Pipeline traceability delivered** - De-identification sessions now automatically link to pipeline cards on job completion, with duplicate prevention and bidirectional references
2. **MongoDB integration completed** - Database provisioning and data access utilities provide a solid persistence foundation for Sprint 3
3. **Entity type filtering implemented** - Users can now scope detection to specific PII categories, directly addressing Sprint 1's core detection limitations
4. **Copilot agent tooling productive** - GitHub Copilot SWE agent enabled fast iteration on implementation; PRs included tests and structured commit messages

---

## What Didn't Go Well

1. **Contribution imbalance continued** - For the second consecutive sprint, three of four team members made zero code contributions. The Sprint 1 action item (1 merged PR per week per member) was not followed by any team member other than Carley.
2. **Retroactive issue tracking** - The majority of Sprint 2 issues were created and closed on the final day of the sprint (3/6/26), indicating the board was updated after the fact rather than used as a live tracking tool during the sprint.
3. **Individual reflections still missing** - Diamond, Sakshi, and Elijah's reflection sections from the Sprint 1 retrospective were never filled in. This document is incomplete until all team members contribute their sections.
4. **Export feature not shipped** - Issue #49 (audit log export) was labeled sprint-2 must-have but the implementing PR (#73) remains unmerged.

---

## Action Items for Next Sprint

1. **Each team member must open and merge at least 1 PR in Sprint 3**
   - Assigned to: Diamond Hogans, Sakshi Patel, Elijah Jenkins
   - Carley will not open PRs on issues assigned to other team members
   - PRs must be human-authored, not Copilot-generated

2. **Update the project board weekly, not on the last day**
   - Assigned to: All team members
   - Issues should move columns as work progresses, not at sprint close

3. **Complete individual reflections for Sprint 1 and Sprint 2 before the next class meeting**
   - Assigned to: Diamond Hogans, Sakshi Patel, Elijah Jenkins
   - Both retrospective documents remain incomplete without these sections

4. **Close Issue #27 (detection rationale) by verifying acceptance criteria**
   - Assigned to: Carley Fant
   - PR #63 ("feat: add Show detection rationale toggle") is open — review and merge or close

5. **Ship Issue #49 (audit log export) in Sprint 3**
   - Assigned to: TBD
   - PR #73 is open; assign a team member to review, test, and merge it

---

## Individual Reflections

**Carley Fant:**
This sprint I led the Taipy-to-v2 migration, set up MongoDB integration, implemented pipeline card traceability, and coordinated issue tracking across the archived and active repositories. For Sprint 3, I want to step back from implementation on issues assigned to other team members and focus on reviewing their PRs instead, so the team builds actual hands-on experience with the codebase.

**Diamond Hogans:**
[Please add 2-4 sentences about your contribution this sprint and one thing you want to improve next sprint]

**Sakshi Patel:**
[Please add 2-4 sentences about your contribution this sprint and one thing you want to improve next sprint]

**Elijah Jenkins:**
[Please add 2-4 sentences about your contribution this sprint and one thing you want to improve next sprint]

---

## Contribution Transparency Note

Per the assignment guidelines, we are documenting that three team members (Diamond Hogans, Sakshi Patel, and Elijah Jenkins) have not made code contributions to the v2 repository during Sprint 2. The majority of technical commits were authored by GitHub Copilot SWE agent (20 commits) rather than human team members. The team is addressing this through the action items above for Sprint 3.

Commit history: [View on GitHub](https://github.com/cpsc4205-group3/anonymous-studio/commits/main)
