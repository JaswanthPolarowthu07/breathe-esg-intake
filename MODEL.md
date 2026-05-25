# MODEL.md

## Core idea

The app separates source truth from analyst judgment:

- `RawRecord` stores the uploaded row exactly as received, with a row hash, parse status, errors, and warnings.
- `ActivityRecord` stores the normalized emissions activity row analysts review. It can be edited until locked.
- `AuditEvent` records every batch ingest, edit, approve, reject, and lock action with before/after snapshots.

That split lets us preserve provenance while still giving analysts a practical queue.

## Tenancy

`Tenant` is the root ownership boundary. `Facility`, `PlantLookup`, `SourceSystem`, `EmissionFactor`, `IngestionBatch`, `ActivityRecord`, and `AuditEvent` all carry a tenant relationship. API calls accept a `tenant` parameter, and all querysets are scoped to that tenant.

For a production product I would enforce tenant scoping in authentication middleware and database-level policies. For this prototype, the model is tenant-safe but the UI uses a tenant selector instead of full auth.

## Source systems

`SourceSystem` identifies the source type and ingestion mode:

- `sap`: CSV upload from S/4HANA material document and purchase order exports.
- `utility`: Monthly utility portal CSV export.
- `travel`: Concur-like JSON or CSV export.

`IngestionBatch` tracks the file, uploader, created/completed timestamps, row counts, failed row counts, duplicate counts, and suspicious row counts.

`RawRecord.row_hash` and `ActivityRecord.raw_fingerprint` support exact duplicate detection. `ActivityRecord.source_record_key` captures the business key, such as a SAP material document item, utility meter-period-bill, or travel trip segment.

## Normalized activity

`ActivityRecord` carries the common review surface:

- Scope: `scope_1`, `scope_2`, `scope_3`.
- Category: examples include `diesel`, `purchased_electricity`, `business_travel_flight`, and `purchased_goods`.
- Dates: `activity_date`, `period_start`, `period_end`.
- Location: `facility`, `plant_code`, and `meter_id`.
- Parties: `supplier`, `vendor`.
- Quantities: original quantity/unit and canonical quantity/unit.
- Finance: spend amount and currency.
- Emissions: emission factor link and calculated `co2e_kg`.
- Review: status, flags, analyst notes, approval identity, approval timestamp, and lock timestamp.

## Scope categorization

- SAP fuel rows become Scope 1 fuel combustion.
- Utility electricity rows become Scope 2 purchased electricity.
- Travel and procurement rows become Scope 3. Travel is business travel; procurement uses a spend proxy only when a better supplier/category factor is unavailable.

Rows with missing factors remain visible but cannot be approved until fixed.

## Unit normalization

The parsers normalize common unit variants:

- Fuel: gallons to liters, liters retained.
- Electricity: MWh to kWh, kWh retained.
- Travel: miles to kilometers, kilometers retained.
- Hotel: nights retained.
- Spend: USD retained for the prototype procurement proxy.

Unsupported units are flagged and usually fail normalization. Informational conversions are retained as quality flags so an analyst can understand why a number changed.

## Audit trail

`AuditEvent` stores:

- Actor.
- Action.
- Linked activity record or batch.
- Before and after snapshots for row-level changes.
- Reason text.
- Timestamp.

Approved records can still be locked. Locked records return HTTP `423` on edit attempts and cannot be rejected through the API.

## Why not one giant emissions table?

A single table would be faster to build, but it would blur three things auditors ask separately: what arrived, what the system inferred, and what an analyst changed. The model keeps those boundaries explicit.
