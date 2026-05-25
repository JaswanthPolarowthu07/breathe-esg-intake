# TRADEOFFS.md

## 1. No full authentication or role system

The app has a reviewer selector that stamps audit events, but it does not require login. I spent the time on tenant-aware data modeling, ingestion, review state, and audit behavior instead. In production, I would add SSO, tenant membership, reviewer/auditor roles, and immutable actor ids.

## 2. No live SAP, utility, or Concur connectors

The prototype uses file uploads for all three sources. That is realistic for onboarding because clients often begin with exports before credentials and security review are complete. Live connectors would need credential storage, retries, incremental sync cursors, webhooks, and data processing agreements.

## 3. No auditor export package

Rows can be approved and locked, and audit history is preserved, but the app does not generate a final auditor evidence pack. I would add export bundles containing locked normalized rows, raw source rows, factor versions, and audit events once the review workflow is accepted.
