# DECISIONS.md

## SAP source

I chose S/4HANA OData/ALV-style CSV exports rather than IDoc ingestion. IDocs are realistic, but a four-day prototype should optimize for the integration path analysts can actually test without SAP credentials: a CSV export containing material document and purchase order item fields.

Handled subset:

- Material document rows for fuel consumption.
- Purchase order item rows for procurement spend.
- Mixed English/German headers such as `Werk`, `Buchungsdatum`, `Menge`, and `Waehrung`.
- Plant code lookup to facilities.
- Liter and gallon fuel quantities.
- USD procurement spend proxy.

Ignored:

- Full IDoc hierarchy and partner profiles.
- SAP unit conversion tables.
- Exchange rates for non-USD procurement.
- Supplier-specific procurement emission factors.

PM questions:

- Which SAP system and module owns fuel usage: MM material movements, fleet cards, PM work orders, or FI invoices?
- Do plant codes already map to reporting facilities?
- Are reversals expected to reduce emissions or should they be separate audit adjustments?

## Utility source

I chose portal CSV export shaped by Green Button concepts. Many facilities teams can download CSV bills or interval usage before API authorization is available.

Handled subset:

- Meter id, account, facility code, utility, service period, usage, usage unit, demand, tariff, cost, currency, bill id, and read type.
- Non-calendar billing periods.
- MWh to kWh conversion.
- Duplicate meter-period detection.
- Estimated reads and long billing periods.

Ignored:

- PDF bill parsing.
- Green Button XML parsing.
- Time-of-use interval allocation.
- Market-based supplier-specific electricity factors.

PM questions:

- Do auditors want bill-level totals, interval-level usage, or both?
- Is the client reporting location-based, market-based, or dual Scope 2?
- Do facilities have sub-meters that should roll up to one site?

## Travel source

I chose a Concur-like itinerary/expense export as JSON or CSV. This matches the shape of travel tools: reports, entries, segment ids, expense types, vendors, dates, and sometimes origin/destination airports without distance.

Handled subset:

- Flight, hotel, rail, taxi/car, and EV ground travel.
- Airport-code distance estimation for known airports.
- Cabin multipliers for premium, business, and first class.
- Hotel nights from explicit night count or check-in/check-out dates.
- Personal expense exclusion.

Ignored:

- Live OAuth/API pull.
- Full PNR lifecycle handling.
- Radiative forcing options.
- Employee home office or commute categories.

PM questions:

- Should personal card travel ever enter the queue, or should it be dropped before ingestion?
- Do we need employee-level reporting, department rollups, or only company totals?
- Which travel factor set do auditors expect?

## Analyst workflow

All normalized rows start as `needs_review` unless they failed. Analysts can edit quantities/notes, approve rows, reject rows, and lock approved rows. Locking is separated from approval because many teams do an internal approval pass before auditor export freeze.

## Emission factors

The prototype uses clearly labeled placeholder factors seeded in the database. This keeps the app behavior complete without pretending those factors are audit-ready. In production, factors should be versioned by source, geography, category, and reporting year.
