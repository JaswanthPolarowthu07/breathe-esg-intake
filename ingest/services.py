import csv
import hashlib
import io
import json
import math
import re
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone as django_timezone

from .models import (
    ActivityRecord,
    AuditEvent,
    EmissionFactor,
    Facility,
    IngestionBatch,
    PlantLookup,
    RawRecord,
    SourceSystem,
    Tenant,
)


UNIT_ALIASES = {
    "L": "L",
    "LTR": "L",
    "LITER": "L",
    "LITRE": "L",
    "LITERS": "L",
    "LITRES": "L",
    "GAL": "gal",
    "GALLON": "gal",
    "GALLONS": "gal",
    "USG": "gal",
    "KWH": "kWh",
    "KW H": "kWh",
    "MWH": "MWh",
    "KM": "km",
    "KILOMETER": "km",
    "KILOMETERS": "km",
    "MI": "mi",
    "MILE": "mi",
    "MILES": "mi",
    "NIGHT": "night",
    "NIGHTS": "night",
    "USD": "USD",
}

SUSPICIOUS_FLAGS = {
    "airport_code_unknown",
    "billing_period_over_45_days",
    "duplicate_meter_period",
    "future_activity_date",
    "high_flight_distance",
    "high_fuel_quantity",
    "high_utility_usage",
    "missing_emission_factor",
    "missing_tariff",
    "negative_quantity_reversal",
    "non_usd_spend_no_fx",
    "source_key_reappeared_with_changed_payload",
    "unknown_facility",
    "unknown_plant_code",
    "unsupported_unit",
    "zero_usage",
}

SAP_ALIASES = {
    "material_document": ["materialdocument", "materialdocumentnumber", "belegnummer", "materialbeleg"],
    "material_document_year": ["materialdocumentyear", "jahr", "geschaftsjahr", "fiscalyear"],
    "material_document_item": ["materialdocumentitem", "item", "position", "zeile"],
    "purchase_order": ["purchaseorder", "purchasingdocument", "einkaufsbeleg", "po"],
    "purchase_order_item": ["purchaseorderitem", "einkaufsbelegposition", "poitem"],
    "document_date": ["documentdate", "postingdate", "buchungsdatum", "belegdatum", "postedon"],
    "plant": ["plant", "werk"],
    "storage_location": ["storagelocation", "lagerort"],
    "movement_type": ["goodsmovementtype", "movementtype", "bewegungsart"],
    "material": ["material", "materialnumber", "artikel"],
    "description": ["materialdescription", "shorttext", "kurztext", "beschreibung", "description"],
    "material_group": ["materialgroup", "warengruppe", "commoditycode"],
    "unit": ["entryunit", "unit", "uom", "erfassme", "mengeneinheit"],
    "quantity": ["quantityinentryunit", "quantity", "menge", "qty"],
    "supplier": ["supplier", "vendor", "lieferant"],
    "amount": ["netamount", "netpriceamount", "amount", "nettowert", "value"],
    "currency": ["currency", "transactioncurrency", "waehrung", "wahrung"],
    "updated_at": ["lastchangedatetime", "changedat", "sourceupdatedat"],
}

UTILITY_ALIASES = {
    "meter_id": ["meterid", "meternumber", "meter", "servicepoint", "usagepoint"],
    "account_number": ["accountnumber", "account", "utilityaccount"],
    "facility_code": ["facilitycode", "sitecode", "buildingcode", "facility"],
    "utility": ["utility", "utilityname", "supplier"],
    "service_start": ["servicestart", "periodstart", "billingstart", "fromdate", "startdate"],
    "service_end": ["serviceend", "periodend", "billingend", "todate", "enddate"],
    "usage": ["usage", "usagequantity", "energy", "consumption", "kwh"],
    "usage_unit": ["usageunit", "unit", "uom"],
    "demand_kw": ["demandkw", "peakdemand", "kwdemand"],
    "tariff": ["tariff", "rate", "rateschedule"],
    "cost": ["cost", "billamount", "totalcharges", "amount"],
    "currency": ["currency"],
    "bill_id": ["billid", "invoice", "invoicenumber"],
    "read_type": ["readtype", "quality", "estimated", "readquality"],
}

TRAVEL_ALIASES = {
    "trip_id": ["tripid", "reportid", "itineraryid", "requestid"],
    "segment_id": ["segmentid", "entryid", "lineid"],
    "traveler": ["traveler", "traveleremail", "employeeemail", "user"],
    "category": ["category", "expensetype", "segmenttype", "spendcategory"],
    "travel_date": ["traveldate", "transactiondate", "startdate", "departuredatetime", "checkindate"],
    "end_date": ["enddate", "returndate", "checkoutdate"],
    "origin": ["fromairport", "originaireport", "origin", "departureairport"],
    "destination": ["toairport", "destinationairport", "destination", "arrivalairport"],
    "distance_km": ["distancekm", "distance", "businessdistance"],
    "distance_unit": ["distanceunit"],
    "cabin": ["cabin", "class", "bookingclass"],
    "nights": ["nights", "hotelnights", "hotelandsleepingroomnights", "hotel_nights"],
    "city": ["city", "hotelcity", "location"],
    "country": ["country", "hotelcountry"],
    "vehicle_type": ["vehicletype", "transportmode", "groundtype"],
    "amount": ["amount", "transactionamount", "approvedamount"],
    "currency": ["currency", "transactioncurrencycode"],
    "vendor": ["vendor", "merchant", "supplier", "airline", "hotel"],
    "personal": ["personal", "ispersonal", "personalflag"],
}

AIRPORTS = {
    "ATL": (33.6407, -84.4277),
    "BLR": (13.1986, 77.7066),
    "BOS": (42.3656, -71.0096),
    "DEL": (28.5562, 77.1000),
    "DEN": (39.8561, -104.6737),
    "DFW": (32.8998, -97.0403),
    "FRA": (50.0379, 8.5622),
    "IAH": (29.9902, -95.3368),
    "JFK": (40.6413, -73.7781),
    "LAX": (33.9416, -118.4085),
    "LHR": (51.4700, -0.4543),
    "ORD": (41.9742, -87.9073),
    "SFO": (37.6213, -122.3790),
}


def normalize_key(value):
    text = str(value or "").strip().lower()
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("ä", "a")
        .replace("ö", "o")
        .replace("ü", "u")
    )
    return re.sub(r"[^a-z0-9]", "", text)


def normalize_row(row):
    return {normalize_key(key): value for key, value in row.items()}


def pick(row, aliases, field):
    normalized = normalize_row(row)
    for alias in aliases[field]:
        if alias in normalized and str(normalized[alias]).strip() != "":
            return normalized[alias]
    return None


def parse_decimal(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def parse_bool(value):
    text = str(value or "").strip().lower()
    return text in {"y", "yes", "true", "1", "personal", "estimated"}


def parse_date(value):
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    match = re.match(r"/Date\((\-?\d+)", text)
    if match:
        return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc).date()
    if re.fullmatch(r"\d+(\.0)?", text):
        serial = int(Decimal(text))
        if 30000 <= serial <= 60000:
            return date(1899, 12, 30) + timedelta(days=serial)
    cleaned = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y%m%d",
        "%d-%m-%Y",
        "%d-%b-%Y",
        "%b %d %Y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(value):
    parsed = parse_date(value)
    if not parsed:
        return None
    return datetime.combine(parsed, datetime.min.time(), tzinfo=timezone.utc)


def normalize_unit(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return UNIT_ALIASES.get(text.upper(), text)


def decimal_to_float(value):
    if value is None:
        return None
    return float(value)


def row_hash(row):
    payload = json.dumps(row, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_upload(uploaded_file, source_type):
    raw = uploaded_file.read()
    text = raw.decode("utf-8-sig")
    stripped = text.strip()
    if source_type == SourceSystem.SourceType.TRAVEL and stripped[:1] in {"[", "{"}:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            for key in ("items", "segments", "entries", "data"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return [payload]
        return payload
    first_line = stripped.splitlines()[0] if stripped else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return list(reader)


def find_factor(tenant, key, unit):
    return (
        EmissionFactor.objects.filter(Q(tenant=tenant) | Q(tenant__isnull=True), key=key, unit=unit)
        .order_by("-tenant_id", "-valid_from")
        .first()
    )


def find_facility(tenant, code=None, meter_id=None):
    if code:
        facility = Facility.objects.filter(tenant=tenant, code__iexact=str(code).strip()).first()
        if facility:
            return facility
    if meter_id:
        for facility in Facility.objects.filter(tenant=tenant):
            aliases = [str(item).lower() for item in facility.meter_aliases]
            if str(meter_id).strip().lower() in aliases:
                return facility
    return None


def facility_for_plant(tenant, plant_code):
    if not plant_code:
        return None
    lookup = (
        PlantLookup.objects.select_related("facility")
        .filter(tenant=tenant, plant_code__iexact=str(plant_code).strip(), active=True)
        .first()
    )
    return lookup.facility if lookup else None


def apply_factor(tenant, factor_key, quantity, unit, flags):
    if quantity is None:
        return None, None
    factor = find_factor(tenant, factor_key, unit)
    if not factor:
        flags.append("missing_emission_factor")
        return None, None
    return factor, quantity * factor.kg_co2e_per_unit


def canonicalize_fuel_quantity(quantity, unit, flags):
    unit = normalize_unit(unit)
    if quantity is None:
        return None, "", "missing_quantity"
    if unit == "L":
        return quantity, "L", None
    if unit == "gal":
        flags.append("unit_converted_gal_to_l")
        return quantity * Decimal("3.785411784"), "L", None
    return quantity, unit, "unsupported_unit"


def canonicalize_natural_gas_quantity(quantity, unit, flags):
    unit = normalize_unit(unit)
    if quantity is None:
        return None, "", "missing_quantity"
    if unit == "kWh":
        return quantity, "kWh", None
    if unit == "MWh":
        flags.append("unit_converted_mwh_to_kwh")
        return quantity * Decimal("1000"), "kWh", None
    return quantity, unit, "unsupported_unit"


def infer_fuel_factor(description, material_group):
    text = f"{description or ''} {material_group or ''}".lower()
    if any(term in text for term in ("gasoline", "petrol", "benzin")):
        return "gasoline_liter"
    if any(term in text for term in ("natural gas", "lng", "cng")):
        return "natural_gas_kwh"
    return "diesel_liter"


def normalize_sap(row, tenant, source_system, fingerprint):
    flags = []
    errors = []
    material_doc = pick(row, SAP_ALIASES, "material_document")
    material_year = pick(row, SAP_ALIASES, "material_document_year")
    material_item = pick(row, SAP_ALIASES, "material_document_item")
    purchase_order = pick(row, SAP_ALIASES, "purchase_order")
    purchase_item = pick(row, SAP_ALIASES, "purchase_order_item")
    plant_code = str(pick(row, SAP_ALIASES, "plant") or "").strip()
    description = str(pick(row, SAP_ALIASES, "description") or "").strip()
    material_group = str(pick(row, SAP_ALIASES, "material_group") or "").strip()
    quantity = parse_decimal(pick(row, SAP_ALIASES, "quantity"))
    unit = normalize_unit(pick(row, SAP_ALIASES, "unit"))
    amount = parse_decimal(pick(row, SAP_ALIASES, "amount"))
    currency = str(pick(row, SAP_ALIASES, "currency") or tenant.default_currency).strip().upper()
    activity_date = parse_date(pick(row, SAP_ALIASES, "document_date"))
    supplier = str(pick(row, SAP_ALIASES, "supplier") or "").strip()
    movement_type = str(pick(row, SAP_ALIASES, "movement_type") or "").strip()

    if any(normalize_key(key) in {"werk", "buchungsdatum", "bewegungsart", "menge", "warengruppe"} for key in row):
        flags.append("sap_german_headers")
    if activity_date and activity_date > date.today():
        flags.append("future_activity_date")

    facility = facility_for_plant(tenant, plant_code)
    if not facility:
        flags.append("unknown_plant_code")

    source_key = None
    if material_doc:
        source_key = f"MATDOC:{material_doc}:{material_year or 'unknown-year'}:{material_item or '0'}"
    elif purchase_order:
        source_key = f"PO:{purchase_order}:{purchase_item or '0'}"
    else:
        errors.append("missing_sap_document_key")
        source_key = f"SAP:unkeyed:{fingerprint[:12]}"

    text = f"{description} {material_group}".lower()
    is_fuel = any(term in text for term in ("fuel", "diesel", "gasoline", "petrol", "benzin", "lng", "cng"))
    if is_fuel:
        factor_key = infer_fuel_factor(description, material_group)
        if factor_key == "natural_gas_kwh":
            canonical_qty, canonical_unit, unit_error = canonicalize_natural_gas_quantity(quantity, unit, flags)
        else:
            canonical_qty, canonical_unit, unit_error = canonicalize_fuel_quantity(quantity, unit, flags)
        if unit_error:
            errors.append(unit_error)
        if quantity is not None and quantity < 0:
            flags.append("negative_quantity_reversal")
        if canonical_qty is not None and abs(canonical_qty) > Decimal("50000"):
            flags.append("high_fuel_quantity")
        factor, co2e = apply_factor(tenant, factor_key, canonical_qty, canonical_unit, flags)
        category = factor_key.replace("_liter", "")
        scope = ActivityRecord.Scope.SCOPE_1
    else:
        if amount is None:
            errors.append("missing_procurement_amount_or_fuel_quantity")
        if currency != "USD":
            flags.append("non_usd_spend_no_fx")
        canonical_qty = amount
        canonical_unit = currency or "USD"
        factor, co2e = apply_factor(tenant, "procurement_spend", canonical_qty, canonical_unit, flags)
        category = "purchased_goods"
        scope = ActivityRecord.Scope.SCOPE_3

    if not activity_date:
        errors.append("unparseable_activity_date")

    return {
        "source_record_key": source_key,
        "source_updated_at": parse_datetime(pick(row, SAP_ALIASES, "updated_at")),
        "scope": scope,
        "category": category,
        "activity_date": activity_date,
        "period_start": None,
        "period_end": None,
        "facility": facility,
        "plant_code": plant_code,
        "meter_id": "",
        "supplier": supplier,
        "vendor": supplier,
        "description": description or material_group or "SAP activity",
        "original_quantity": quantity,
        "original_unit": unit,
        "canonical_quantity": canonical_qty,
        "canonical_unit": canonical_unit,
        "spend_amount": amount,
        "currency": currency,
        "emission_factor": factor,
        "co2e_kg": co2e,
        "quality_flags": flags + errors,
        "errors": errors,
        "normalized_payload": {
            "material_document": material_doc,
            "purchase_order": purchase_order,
            "movement_type": movement_type,
            "material_group": material_group,
        },
    }


def last_day_of_month(value):
    return monthrange(value.year, value.month)[1]


def normalize_utility(row, tenant, source_system, fingerprint):
    flags = []
    errors = []
    meter_id = str(pick(row, UTILITY_ALIASES, "meter_id") or "").strip()
    facility_code = str(pick(row, UTILITY_ALIASES, "facility_code") or "").strip()
    facility = find_facility(tenant, facility_code, meter_id)
    start = parse_date(pick(row, UTILITY_ALIASES, "service_start"))
    end = parse_date(pick(row, UTILITY_ALIASES, "service_end"))
    usage = parse_decimal(pick(row, UTILITY_ALIASES, "usage"))
    demand_kw = parse_decimal(pick(row, UTILITY_ALIASES, "demand_kw"))
    unit = normalize_unit(pick(row, UTILITY_ALIASES, "usage_unit") or "kWh")
    cost = parse_decimal(pick(row, UTILITY_ALIASES, "cost"))
    currency = str(pick(row, UTILITY_ALIASES, "currency") or tenant.default_currency).strip().upper()
    tariff = str(pick(row, UTILITY_ALIASES, "tariff") or "").strip()
    utility = str(pick(row, UTILITY_ALIASES, "utility") or "Utility portal").strip()
    bill_id = str(pick(row, UTILITY_ALIASES, "bill_id") or "").strip()
    read_type = str(pick(row, UTILITY_ALIASES, "read_type") or "").strip()

    if not facility:
        flags.append("unknown_facility")
    if not start or not end:
        errors.append("missing_or_unparseable_billing_period")
    elif end < start:
        errors.append("billing_period_end_before_start")
    else:
        days = max((end - start).days + 1, 1)
        if days > 45:
            flags.append("billing_period_over_45_days")
        if start.day != 1 or end.day != last_day_of_month(end):
            flags.append("non_calendar_billing_period")
    if not tariff:
        flags.append("missing_tariff")
    if read_type and ("estimate" in read_type.lower() or parse_bool(read_type)):
        flags.append("estimated_meter_read")

    if usage is None:
        if demand_kw is not None:
            errors.append("demand_present_without_energy_usage")
        else:
            errors.append("missing_usage")

    canonical_qty = usage
    canonical_unit = unit
    if usage is not None:
        if unit == "MWh":
            canonical_qty = usage * Decimal("1000")
            canonical_unit = "kWh"
            flags.append("unit_converted_mwh_to_kwh")
        elif unit != "kWh":
            errors.append("unsupported_unit")
        if usage == 0:
            flags.append("zero_usage")
        if start and end:
            usage_per_day = canonical_qty / Decimal(max((end - start).days + 1, 1))
            if usage_per_day > Decimal("50000"):
                flags.append("high_utility_usage")

    source_key = f"UTILITY:{meter_id or facility_code or 'unknown'}:{start or 'unknown'}:{end or 'unknown'}:{bill_id or 'no-bill'}"
    if (
        meter_id
        and start
        and end
        and ActivityRecord.objects.filter(
            tenant=tenant,
            source_system=source_system,
            meter_id=meter_id,
            period_start=start,
            period_end=end,
        ).exists()
    ):
        flags.append("duplicate_meter_period")

    factor_key = "electricity_de_grid_kwh" if facility and facility.country == "DE" else "electricity_us_grid_kwh"
    factor, co2e = apply_factor(tenant, factor_key, canonical_qty, "kWh", flags)

    return {
        "source_record_key": source_key,
        "source_updated_at": None,
        "scope": ActivityRecord.Scope.SCOPE_2,
        "category": "purchased_electricity",
        "activity_date": end,
        "period_start": start,
        "period_end": end,
        "facility": facility,
        "plant_code": facility_code,
        "meter_id": meter_id,
        "supplier": utility,
        "vendor": utility,
        "description": f"{utility} electricity bill {bill_id}".strip(),
        "original_quantity": usage,
        "original_unit": unit,
        "canonical_quantity": canonical_qty,
        "canonical_unit": "kWh" if not errors else canonical_unit,
        "spend_amount": cost,
        "currency": currency,
        "emission_factor": factor,
        "co2e_kg": co2e,
        "quality_flags": flags + errors,
        "errors": errors,
        "normalized_payload": {
            "account_number": pick(row, UTILITY_ALIASES, "account_number"),
            "demand_kw": decimal_to_float(demand_kw),
            "tariff": tariff,
            "read_type": read_type,
        },
    }


def airport_distance_km(origin, destination):
    origin = str(origin or "").strip().upper()
    destination = str(destination or "").strip().upper()
    if origin not in AIRPORTS or destination not in AIRPORTS:
        return None
    lat1, lon1 = AIRPORTS[origin]
    lat2, lon2 = AIRPORTS[destination]
    radius = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return Decimal(str(round(radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)))


def normalize_distance(value, unit, flags):
    distance = parse_decimal(value)
    if distance is None:
        return None
    normalized_unit = normalize_unit(unit or "km")
    if normalized_unit == "mi":
        flags.append("unit_converted_miles_to_km")
        return distance * Decimal("1.609344")
    return distance


def travel_factor_for_flight(distance_km):
    if distance_km is None:
        return "flight_unknown_km"
    if distance_km < Decimal("700"):
        return "flight_short_haul_km"
    if distance_km < Decimal("3700"):
        return "flight_medium_haul_km"
    return "flight_long_haul_km"


def cabin_multiplier(cabin):
    text = str(cabin or "").strip().lower()
    if "first" in text:
        return Decimal("2.00"), "cabin_multiplier_first"
    if "business" in text:
        return Decimal("1.50"), "cabin_multiplier_business"
    if "premium" in text:
        return Decimal("1.20"), "cabin_multiplier_premium_economy"
    return Decimal("1.00"), ""


def normalize_travel(row, tenant, source_system, fingerprint):
    flags = []
    errors = []
    trip_id = str(pick(row, TRAVEL_ALIASES, "trip_id") or "trip").strip()
    segment_id = str(pick(row, TRAVEL_ALIASES, "segment_id") or fingerprint[:8]).strip()
    category_text = str(pick(row, TRAVEL_ALIASES, "category") or "").strip().lower()
    activity_date = parse_date(pick(row, TRAVEL_ALIASES, "travel_date"))
    end_date = parse_date(pick(row, TRAVEL_ALIASES, "end_date"))
    vendor = str(pick(row, TRAVEL_ALIASES, "vendor") or "").strip()
    traveler = str(pick(row, TRAVEL_ALIASES, "traveler") or "").strip()
    amount = parse_decimal(pick(row, TRAVEL_ALIASES, "amount"))
    currency = str(pick(row, TRAVEL_ALIASES, "currency") or tenant.default_currency).strip().upper()

    if parse_bool(pick(row, TRAVEL_ALIASES, "personal")):
        errors.append("personal_expense_excluded")
    if not activity_date:
        errors.append("missing_or_unparseable_travel_date")
    if activity_date and activity_date > date.today():
        flags.append("future_activity_date")

    source_key = f"TRAVEL:{trip_id}:{segment_id}"
    scope = ActivityRecord.Scope.SCOPE_3
    original_quantity = None
    original_unit = ""
    canonical_qty = None
    canonical_unit = ""
    category = "business_travel"
    factor = None
    co2e = None
    description = category_text or "Travel activity"
    normalized_payload = {"traveler": traveler, "trip_id": trip_id, "segment_id": segment_id}

    if "air" in category_text or "flight" in category_text:
        origin = str(pick(row, TRAVEL_ALIASES, "origin") or "").strip().upper()
        destination = str(pick(row, TRAVEL_ALIASES, "destination") or "").strip().upper()
        distance = normalize_distance(
            pick(row, TRAVEL_ALIASES, "distance_km"),
            pick(row, TRAVEL_ALIASES, "distance_unit"),
            flags,
        )
        if distance is None:
            distance = airport_distance_km(origin, destination)
            if distance is None:
                errors.append("airport_code_unknown")
            else:
                flags.append("distance_estimated_from_airports")
        multiplier, multiplier_flag = cabin_multiplier(pick(row, TRAVEL_ALIASES, "cabin"))
        if multiplier_flag:
            flags.append(multiplier_flag)
        adjusted_distance = distance * multiplier if distance is not None else None
        if distance is not None and distance > Decimal("16000"):
            flags.append("high_flight_distance")
        factor_key = travel_factor_for_flight(distance)
        factor, co2e = apply_factor(tenant, factor_key, adjusted_distance, "km", flags)
        original_quantity = distance
        original_unit = "km"
        canonical_qty = adjusted_distance
        canonical_unit = "km"
        category = "business_travel_flight"
        description = f"Flight {origin or '?'} to {destination or '?'}"
        normalized_payload.update({"origin": origin, "destination": destination, "cabin_multiplier": str(multiplier)})
    elif "hotel" in category_text or "lodging" in category_text:
        nights = parse_decimal(pick(row, TRAVEL_ALIASES, "nights"))
        if nights is None and activity_date and end_date:
            nights = Decimal(max((end_date - activity_date).days, 1))
            flags.append("nights_derived_from_dates")
        if nights is None:
            errors.append("missing_hotel_nights")
        country = str(pick(row, TRAVEL_ALIASES, "country") or "US").strip().upper()
        factor_key = "hotel_night_de" if country == "DE" else "hotel_night_us"
        factor, co2e = apply_factor(tenant, factor_key, nights, "night", flags)
        original_quantity = nights
        original_unit = "night"
        canonical_qty = nights
        canonical_unit = "night"
        category = "business_travel_hotel"
        description = f"Hotel stay {pick(row, TRAVEL_ALIASES, 'city') or ''}".strip()
        normalized_payload.update({"country": country, "city": pick(row, TRAVEL_ALIASES, "city")})
    elif any(term in category_text for term in ("ground", "taxi", "car", "rail", "train", "rideshare")):
        distance = normalize_distance(
            pick(row, TRAVEL_ALIASES, "distance_km"),
            pick(row, TRAVEL_ALIASES, "distance_unit"),
            flags,
        )
        if distance is None:
            errors.append("missing_ground_distance")
        vehicle_type = str(pick(row, TRAVEL_ALIASES, "vehicle_type") or category_text).lower()
        if "rail" in vehicle_type or "train" in vehicle_type:
            factor_key = "ground_rail_km"
        elif "ev" in vehicle_type or "electric" in vehicle_type:
            factor_key = "ground_ev_km"
        else:
            factor_key = "ground_car_km"
        factor, co2e = apply_factor(tenant, factor_key, distance, "km", flags)
        original_quantity = distance
        original_unit = "km"
        canonical_qty = distance
        canonical_unit = "km"
        category = "business_travel_ground"
        description = f"Ground transport - {vehicle_type}"
        normalized_payload.update({"vehicle_type": vehicle_type})
    else:
        errors.append("unsupported_travel_category")

    return {
        "source_record_key": source_key,
        "source_updated_at": None,
        "scope": scope,
        "category": category,
        "activity_date": activity_date,
        "period_start": activity_date,
        "period_end": end_date or activity_date,
        "facility": None,
        "plant_code": "",
        "meter_id": "",
        "supplier": vendor,
        "vendor": vendor,
        "description": description,
        "original_quantity": original_quantity,
        "original_unit": original_unit,
        "canonical_quantity": canonical_qty,
        "canonical_unit": canonical_unit,
        "spend_amount": amount,
        "currency": currency,
        "emission_factor": factor,
        "co2e_kg": co2e,
        "quality_flags": flags + errors,
        "errors": errors,
        "normalized_payload": normalized_payload,
    }


NORMALIZERS = {
    SourceSystem.SourceType.SAP: normalize_sap,
    SourceSystem.SourceType.UTILITY: normalize_utility,
    SourceSystem.SourceType.TRAVEL: normalize_travel,
}


def serialize_for_audit(record):
    return {
        "id": record.id,
        "status": record.status,
        "scope": record.scope,
        "category": record.category,
        "canonical_quantity": str(record.canonical_quantity) if record.canonical_quantity is not None else None,
        "canonical_unit": record.canonical_unit,
        "spend_amount": str(record.spend_amount) if record.spend_amount is not None else None,
        "currency": record.currency,
        "co2e_kg": str(record.co2e_kg) if record.co2e_kg is not None else None,
        "quality_flags": record.quality_flags,
        "analyst_notes": record.analyst_notes,
    }


def create_failed_activity(tenant, source_system, batch, raw_record, fingerprint, errors):
    return ActivityRecord.objects.create(
        tenant=tenant,
        batch=batch,
        raw_record=raw_record,
        source_system=source_system,
        source_record_key=f"{source_system.source_type}:failed:{batch.id}:{raw_record.row_number}",
        raw_fingerprint=fingerprint,
        scope=ActivityRecord.Scope.SCOPE_3,
        category="unclassified",
        description="Row failed normalization",
        status=ActivityRecord.Status.FAILED,
        quality_flags=errors,
        normalized_payload={"errors": errors},
    )


@transaction.atomic
def ingest_rows(tenant, source_type, rows, filename, source_name=None, actor="Demo Analyst"):
    if source_type not in NORMALIZERS:
        raise ValueError(f"Unsupported source type: {source_type}")
    source_system, _ = SourceSystem.objects.get_or_create(
        tenant=tenant,
        source_type=source_type,
        name=source_name or default_source_name(source_type),
        defaults={"ingestion_mode": default_ingestion_mode(source_type)},
    )
    batch = IngestionBatch.objects.create(
        tenant=tenant,
        source_system=source_system,
        filename=filename,
        uploaded_by=actor,
        total_rows=len(rows),
    )
    normalized = failed = suspicious = duplicate = 0
    normalizer = NORMALIZERS[source_type]

    for index, row in enumerate(rows, start=1):
        fingerprint = row_hash(row)
        raw_record = RawRecord.objects.create(
            batch=batch,
            row_number=index,
            raw_data=row,
            row_hash=fingerprint,
            parse_status=RawRecord.ParseStatus.NORMALIZED,
        )
        try:
            normalized_payload = normalizer(row, tenant, source_system, fingerprint)
        except Exception as exc:
            failed += 1
            raw_record.parse_status = RawRecord.ParseStatus.FAILED
            raw_record.errors = [f"normalizer_exception: {exc}"]
            raw_record.save(update_fields=["parse_status", "errors"])
            create_failed_activity(tenant, source_system, batch, raw_record, fingerprint, raw_record.errors)
            continue

        errors = normalized_payload.pop("errors")
        key = normalized_payload["source_record_key"]
        if ActivityRecord.objects.filter(
            tenant=tenant,
            source_system=source_system,
            source_record_key=key,
            raw_fingerprint=fingerprint,
        ).exists():
            duplicate += 1
            raw_record.parse_status = RawRecord.ParseStatus.DUPLICATE
            raw_record.warnings = ["duplicate_exact_source_row"]
            raw_record.save(update_fields=["parse_status", "warnings"])
            continue
        if ActivityRecord.objects.filter(tenant=tenant, source_system=source_system, source_record_key=key).exists():
            normalized_payload["quality_flags"].append("source_key_reappeared_with_changed_payload")

        status = ActivityRecord.Status.FAILED if errors else ActivityRecord.Status.NEEDS_REVIEW
        try:
            record = ActivityRecord.objects.create(
                tenant=tenant,
                batch=batch,
                raw_record=raw_record,
                source_system=source_system,
                raw_fingerprint=fingerprint,
                status=status,
                **normalized_payload,
            )
        except IntegrityError:
            duplicate += 1
            raw_record.parse_status = RawRecord.ParseStatus.DUPLICATE
            raw_record.warnings = ["duplicate_exact_source_row"]
            raw_record.save(update_fields=["parse_status", "warnings"])
            continue

        if errors:
            failed += 1
            raw_record.parse_status = RawRecord.ParseStatus.FAILED
            raw_record.errors = errors
        else:
            normalized += 1
            raw_record.warnings = record.quality_flags
        raw_record.save(update_fields=["parse_status", "errors", "warnings"])
        if set(record.quality_flags) & SUSPICIOUS_FLAGS:
            suspicious += 1

    batch.normalized_rows = normalized
    batch.failed_rows = failed
    batch.suspicious_rows = suspicious
    batch.duplicate_rows = duplicate
    batch.status = IngestionBatch.Status.COMPLETED
    batch.completed_at = django_timezone.now()
    batch.save()
    AuditEvent.objects.create(
        tenant=tenant,
        batch=batch,
        actor=actor,
        action="batch_ingested",
        after={
            "source_type": source_type,
            "filename": filename,
            "rows": len(rows),
            "normalized": normalized,
            "failed": failed,
            "suspicious": suspicious,
            "duplicates": duplicate,
        },
    )
    return batch


def ingest_file(tenant, source_type, uploaded_file, source_name=None, actor="Demo Analyst"):
    rows = read_upload(uploaded_file, source_type)
    return ingest_rows(
        tenant=tenant,
        source_type=source_type,
        rows=rows,
        filename=getattr(uploaded_file, "name", f"{source_type}-upload"),
        source_name=source_name,
        actor=actor,
    )


def default_source_name(source_type):
    return {
        SourceSystem.SourceType.SAP: "SAP S/4HANA OData export",
        SourceSystem.SourceType.UTILITY: "Utility portal CSV",
        SourceSystem.SourceType.TRAVEL: "Concur travel export",
    }[source_type]


def default_ingestion_mode(source_type):
    return {
        SourceSystem.SourceType.SAP: "CSV upload from S/4HANA OData or ALV extract",
        SourceSystem.SourceType.UTILITY: "Monthly portal CSV upload",
        SourceSystem.SourceType.TRAVEL: "Concur-like JSON or CSV export upload",
    }[source_type]


def recompute_record(record):
    flags = list(record.quality_flags or [])
    if "manual_edit_recomputed" not in flags:
        flags.append("manual_edit_recomputed")
    factor = record.emission_factor
    if not factor and record.category == "purchased_electricity":
        factor = find_factor(record.tenant, "electricity_us_grid_kwh", "kWh")
    if factor and record.canonical_quantity is not None:
        record.co2e_kg = record.canonical_quantity * factor.kg_co2e_per_unit
        record.emission_factor = factor
    record.quality_flags = flags
    return record


def ensure_demo_tenant():
    tenant, _ = Tenant.objects.get_or_create(
        slug="acme-global",
        defaults={"name": "ACME Global Manufacturing", "default_currency": "USD"},
    )
    houston, _ = Facility.objects.get_or_create(
        tenant=tenant,
        code="HOU-PLANT",
        defaults={
            "name": "Houston Assembly Plant",
            "country": "US",
            "region": "Texas",
            "meter_aliases": ["TX-44319", "MTR-HOU-1"],
        },
    )
    berlin, _ = Facility.objects.get_or_create(
        tenant=tenant,
        code="BER-PLANT",
        defaults={
            "name": "Berlin Components Plant",
            "country": "DE",
            "region": "Berlin",
            "meter_aliases": ["DE-77881"],
        },
    )
    austin, _ = Facility.objects.get_or_create(
        tenant=tenant,
        code="AUS-DC",
        defaults={
            "name": "Austin Distribution Center",
            "country": "US",
            "region": "Texas",
            "meter_aliases": ["TX-88312"],
        },
    )
    for plant_code, facility, label in (
        ("1000", houston, "US main manufacturing"),
        ("DE01", berlin, "Germany production"),
        ("2100", austin, "US distribution"),
    ):
        PlantLookup.objects.get_or_create(
            tenant=tenant,
            plant_code=plant_code,
            defaults={"facility": facility, "label": label},
        )
    for source_type in SourceSystem.SourceType.values:
        SourceSystem.objects.get_or_create(
            tenant=tenant,
            source_type=source_type,
            name=default_source_name(source_type),
            defaults={"ingestion_mode": default_ingestion_mode(source_type)},
        )
    seed_factors(tenant)
    return tenant


def seed_factors(tenant):
    factors = [
        ("diesel_liter", "Diesel combustion", "L", "2.680000", "Prototype factor based on common EPA/DEFRA-style diesel factors."),
        ("gasoline_liter", "Gasoline combustion", "L", "2.310000", "Prototype factor based on common EPA/DEFRA-style gasoline factors."),
        ("natural_gas_kwh", "Natural gas combustion", "kWh", "0.184000", "Prototype stationary fuel factor."),
        ("procurement_spend", "Purchased goods spend proxy", "USD", "0.250000", "Prototype spend factor; replace with supplier/category factors."),
        ("electricity_us_grid_kwh", "US grid electricity", "kWh", "0.386000", "Prototype location-based electricity factor."),
        ("electricity_de_grid_kwh", "Germany grid electricity", "kWh", "0.350000", "Prototype location-based electricity factor."),
        ("flight_short_haul_km", "Short-haul economy flight", "km", "0.158000", "Prototype flight factor."),
        ("flight_medium_haul_km", "Medium-haul economy flight", "km", "0.110000", "Prototype flight factor."),
        ("flight_long_haul_km", "Long-haul economy flight", "km", "0.095000", "Prototype flight factor."),
        ("hotel_night_us", "US hotel night", "night", "22.000000", "Prototype hotel factor."),
        ("hotel_night_de", "Germany hotel night", "night", "18.000000", "Prototype hotel factor."),
        ("ground_car_km", "Ground car/taxi", "km", "0.171000", "Prototype ground transport factor."),
        ("ground_rail_km", "Rail transport", "km", "0.035000", "Prototype ground rail factor."),
        ("ground_ev_km", "Electric vehicle ground transport", "km", "0.055000", "Prototype EV transport factor."),
    ]
    for key, label, unit, factor, source in factors:
        EmissionFactor.objects.get_or_create(
            tenant=tenant,
            key=key,
            unit=unit,
            defaults={
                "label": label,
                "kg_co2e_per_unit": Decimal(factor),
                "source": source,
                "valid_from": date(2024, 1, 1),
            },
        )
