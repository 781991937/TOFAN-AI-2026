# TOFAN Smart Academy — Release Gate 1–17

This gate treats the project as complete only when the full path works:

**UI → API → authorization → database/services → persisted data → result → verification**

## Gates
1. Mobile experience: all student panels are reachable from the single web shell and core modules are loaded.
2. Navigation: curriculum, course, lesson, notifications, progress, certificates, profile, assessments and access flows share the same application shell.
3. Student screens: curriculum, lesson/teacher, files, notifications, progress, certificates, profile, assessments and subscriptions are wired.
4. Assessments: discover → load/generate → answer → submit → grade → persist.
5. Results: score, pass/fail, per-question details and course analysis are returned and rendered.
6. Notifications: student list/read and owner/admin broadcast endpoints exist.
7. Subscriptions: stage selection → payment request → proof upload → administrative confirmation/rejection → access.
8. Subscription administration: manager payment queue exposes status, proof and confirmation/rejection actions.
9. Notification administration: broadcast and per-user audit/readback endpoints are protected.
10. AI agents: owner/admin can list, bootstrap, activate/pause and configure tools; manager/teacher runtime endpoints are protected.
11. API contract: `/api/contract` is the stable route map and contract version.
12. API binding: student modules call server APIs rather than local mock state.
13. Academic data lifecycle: curriculum → course → unit → lesson/file → teaching/progress → assessment → result.
14. PostgreSQL production: production startup rejects SQLite and enables PostgreSQL pooling.
15. File storage: uploaded content must use a configured production object-storage adapter before production deployment.
16. Authorization: student resources are owner-scoped; admin/manager operations require owner/admin authorization.
17. Performance/security: CI, smoke tests, syntax checks, readiness and authorization tests must pass before release.

## Current engineering rule
A file existing in the repository is not considered proof of completion. Each gate requires an executable path or a deterministic test.

## Release commands
- Python compile check
- Frontend JavaScript syntax checks
- FastAPI import
- pytest
- application `/health`
- application `/ready`
- API contract verification

## Remaining production prerequisite
Object storage must be configured with a production adapter (S3-compatible or equivalent) and local filesystem storage must remain development-only. This is intentionally a hard release gate rather than a silent fallback.