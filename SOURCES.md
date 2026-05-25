# SOURCES.md

## SAP fuel and procurement

Researched formats:

- SAP S/4HANA Material Document OData service examples for fields like `Material`, `Plant`, `StorageLocation`, `GoodsMovementType`, `EntryUnit`, and `QuantityInEntryUnit`: https://help.sap.com/docs/SAP_S4HANA_CLOUD/3f57e7df4a114edabffe8b2d581a59ed/8bb0d08295044ee3af444b4f2a6e4457.html
- SAP API CDS views for purchase order fields including company code, supplying plant, material group, and supplier material number: https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/af9ef57f504840d2b81be8667206d485/1d6f6bea1c3b4f049742e15a81ff86a0.html
- SAP Cloud SDK purchase order item docs noting plant, units, net price amount, and order/price unit conversion complexity: https://help.sap.com/doc/1fd0ac329d664076acfd210249536594/1.0/en-US/classes/_sap_cloud_sdk_vdm_purchase_order_service.purchaseorderitem.html

What I learned:

- SAP rows are often business-object exports, not clean ESG rows.
- Plant codes need lookup tables.
- Quantity unit and pricing unit are not always the same.
- Header language and customer configuration change column names.

Sample data:

`sample_data/sap_material_procurement_export.csv` includes material document fuel rows, purchase order procurement rows, German-like headers, gallons, reversals, unknown plant codes, EUR spend, and a future-dated activity.

What would break in real deployment:

- SAP unit conversion should come from SAP material/unit tables.
- Procurement should use supplier/category factors, not a spend proxy.
- Reversals need agreed accounting treatment.
- Delta sync needs source update timestamps and cursor state.

## Utility electricity

Researched formats:

- Green Button FAQ describing interval/monthly usage, billing data, multiple usage points, and the ESPI basis: https://green-button.github.io/faq/
- UtilityAPI Green Button XML docs describing utility customer account, bill, usage data, atom feeds, UsagePoint, MeterReading, IntervalBlock, and UsageSummary objects: https://utilityapi.com/docs/greenbutton/xml

What I learned:

- Electricity data often arrives by meter/usage point, not facility.
- Billing periods often do not align with calendar months.
- Usage, demand, tariff, cost, and estimated/actual reads matter separately.
- Larger clients may have multiple meters per facility.

Sample data:

`sample_data/utility_portal_greenbutton_like.csv` includes meter ids, account numbers, service periods, kWh/MWh units, tariff names, demand, cost, estimated reads, duplicates, missing usage, and end-before-start errors.

What would break in real deployment:

- PDF bills need document extraction and human reconciliation.
- Green Button XML should be parsed natively rather than flattened to CSV.
- Market-based Scope 2 needs supplier contracts and renewable attributes.
- Interval data needs aggregation and gap filling.

## Corporate travel

Researched formats:

- SAP Concur itinerary details for record locators, ticket numbers, itinerary source, vendors, hotel/car/air segment details: https://help.sap.com/docs/SAP_CONCUR/92814b27ae9c4b298c6e80d2a3241445/1c431f2e700b1014a46a108435d32877.html
- SAP Concur report entry data for transaction type, transaction date, personal flag, amount, and expense entry fields: https://help.sap.com/docs/CONCUR_EXPENSE/bb83754b1c5541808d50c09901e11475/c89376c016964053927f3f5474311d12.html
- SAP Concur Expense Configuration API docs for policies, expense types, payment types, and authenticated API access patterns: https://preview.developer.concur.com/api-reference/expense/expense-config/v4.expense.config.html

What I learned:

- Travel platforms expose both itinerary and expense concepts.
- Expense type/category drives emission factor selection.
- Flights may provide airport codes without distance.
- Personal expenses need special treatment.

Sample data:

`sample_data/concur_travel_export.json` includes flights, hotel, taxi, train, airport-code distance estimation, cabin class, personal travel exclusion, missing airport code failure, and high-distance flagging.

What would break in real deployment:

- Airport and rail routing should use a complete reference dataset.
- Concur/Navan API access requires OAuth, scopes, and customer approval.
- Travel corrections and cancellations need idempotent state handling.
- Factor choice can vary by cabin, haul length, radiative forcing policy, and reporting standard.
