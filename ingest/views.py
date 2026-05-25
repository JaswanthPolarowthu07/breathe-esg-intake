from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from django.db.models import Count, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import ActivityRecord, AuditEvent, Facility, IngestionBatch, SourceSystem, Tenant
from .serializers import (
    ActivityRecordSerializer,
    AuditEventSerializer,
    BatchSerializer,
    FacilitySerializer,
    SourceSystemSerializer,
    TenantSerializer,
)
from .services import (
    SUSPICIOUS_FLAGS,
    ensure_demo_tenant,
    ingest_file,
    parse_date,
    parse_decimal,
    recompute_record,
    serialize_for_audit,
)


def actor_from(request):
    return request.headers.get("X-Analyst") or request.data.get("actor") or "Demo Analyst"


def get_tenant(request):
    tenant_id = request.query_params.get("tenant") or request.data.get("tenant")
    if tenant_id:
        return get_object_or_404(Tenant, id=tenant_id)
    tenant = Tenant.objects.first()
    return tenant or ensure_demo_tenant()


def money(value):
    return float(value or Decimal("0"))


@api_view(["GET"])
def tenants(request):
    if not Tenant.objects.exists():
        ensure_demo_tenant()
    return Response(TenantSerializer(Tenant.objects.all(), many=True).data)


@api_view(["GET"])
def facilities(request):
    tenant = get_tenant(request)
    return Response(FacilitySerializer(Facility.objects.filter(tenant=tenant), many=True).data)


@api_view(["GET"])
def source_systems(request):
    tenant = get_tenant(request)
    return Response(SourceSystemSerializer(SourceSystem.objects.filter(tenant=tenant), many=True).data)


@api_view(["GET"])
def overview(request):
    tenant = get_tenant(request)
    records = ActivityRecord.objects.filter(tenant=tenant)
    batches = IngestionBatch.objects.filter(tenant=tenant)
    total_co2e = records.exclude(status=ActivityRecord.Status.REJECTED).aggregate(total=Sum("co2e_kg"))["total"]
    status_counts = dict(records.values_list("status").annotate(count=Count("id")))
    scope_counts = dict(records.values_list("scope").annotate(count=Count("id")))
    source_counts = {
        row["source_system__source_type"]: row["count"]
        for row in records.values("source_system__source_type").annotate(count=Count("id"))
    }
    emissions_by_scope = {
        row["scope"]: money(row["total"])
        for row in records.exclude(status=ActivityRecord.Status.REJECTED)
        .values("scope")
        .annotate(total=Sum("co2e_kg"))
    }
    source_health = []
    for source_type in SourceSystem.SourceType.values:
        source_records = records.filter(source_system__source_type=source_type)
        source_batches = batches.filter(source_system__source_type=source_type)
        suspicious_rows = 0
        for flag_list in source_records.values_list("quality_flags", flat=True):
            if set(flag_list or []) & SUSPICIOUS_FLAGS:
                suspicious_rows += 1
        source_health.append(
            {
                "source_type": source_type,
                "rows": source_records.count(),
                "failed": source_records.filter(status=ActivityRecord.Status.FAILED).count(),
                "needs_review": source_records.filter(status=ActivityRecord.Status.NEEDS_REVIEW).count(),
                "approved": source_records.filter(status=ActivityRecord.Status.APPROVED).count(),
                "locked": source_records.filter(status=ActivityRecord.Status.LOCKED).count(),
                "rejected": source_records.filter(status=ActivityRecord.Status.REJECTED).count(),
                "suspicious_rows": suspicious_rows,
                "batch_suspicious": source_batches.aggregate(total=Sum("suspicious_rows"))["total"] or 0,
                "latest_batch": BatchSerializer(source_batches.first()).data if source_batches.exists() else None,
            }
        )
    flags = Counter()
    for flag_list in records.values_list("quality_flags", flat=True):
        flags.update(flag_list or [])
    monthly = defaultdict(Decimal)
    for record in records.exclude(status=ActivityRecord.Status.REJECTED).exclude(activity_date=None):
        month = record.activity_date.strftime("%Y-%m")
        monthly[month] += record.co2e_kg or Decimal("0")
    return Response(
        {
            "tenant": TenantSerializer(tenant).data,
            "totals": {
                "records": records.count(),
                "batches": batches.count(),
                "co2e_kg": money(total_co2e),
                "needs_review": status_counts.get(ActivityRecord.Status.NEEDS_REVIEW, 0),
                "failed": status_counts.get(ActivityRecord.Status.FAILED, 0),
                "approved": status_counts.get(ActivityRecord.Status.APPROVED, 0),
                "locked": status_counts.get(ActivityRecord.Status.LOCKED, 0),
                "rejected": status_counts.get(ActivityRecord.Status.REJECTED, 0),
            },
            "status_counts": status_counts,
            "scope_counts": scope_counts,
            "source_counts": source_counts,
            "emissions_by_scope": emissions_by_scope,
            "source_health": source_health,
            "top_flags": [{"flag": flag, "count": count} for flag, count in flags.most_common(8)],
            "monthly": [{"month": key, "co2e_kg": money(value)} for key, value in sorted(monthly.items())],
            "recent_batches": BatchSerializer(batches[:8], many=True).data,
        }
    )


@api_view(["GET"])
def batches(request):
    tenant = get_tenant(request)
    queryset = IngestionBatch.objects.filter(tenant=tenant).select_related("source_system")
    return Response(BatchSerializer(queryset[:50], many=True).data)


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def ingest(request, source_type):
    tenant = get_tenant(request)
    if source_type not in SourceSystem.SourceType.values:
        return Response({"detail": "Unsupported source type."}, status=status.HTTP_400_BAD_REQUEST)
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return Response({"detail": "Upload a file field named 'file'."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        batch = ingest_file(
            tenant=tenant,
            source_type=source_type,
            uploaded_file=uploaded_file,
            source_name=request.data.get("source_name"),
            actor=actor_from(request),
        )
    except Exception as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(BatchSerializer(batch).data, status=status.HTTP_201_CREATED)


def filtered_records(request):
    tenant = get_tenant(request)
    records = (
        ActivityRecord.objects.filter(tenant=tenant)
        .select_related("source_system", "facility", "emission_factor", "raw_record")
        .order_by("-created_at")
    )
    if request.query_params.get("status"):
        records = records.filter(status=request.query_params["status"])
    if request.query_params.get("source"):
        records = records.filter(source_system__source_type=request.query_params["source"])
    if request.query_params.get("scope"):
        records = records.filter(scope=request.query_params["scope"])
    if request.query_params.get("flag"):
        flag = request.query_params["flag"]
        ids = [record.id for record in records if flag in (record.quality_flags or [])]
        records = ActivityRecord.objects.filter(id__in=ids).select_related(
            "source_system", "facility", "emission_factor", "raw_record"
        )
    if request.query_params.get("q"):
        q = request.query_params["q"]
        records = records.filter(
            source_record_key__icontains=q
        ) | records.filter(description__icontains=q) | records.filter(vendor__icontains=q)
    return records


@api_view(["GET"])
def records(request):
    limit = min(int(request.query_params.get("limit", 200)), 500)
    return Response(ActivityRecordSerializer(filtered_records(request)[:limit], many=True).data)


@api_view(["GET", "PATCH"])
def record_detail(request, record_id):
    tenant = get_tenant(request)
    record = get_object_or_404(
        ActivityRecord.objects.select_related("source_system", "facility", "emission_factor", "raw_record"),
        id=record_id,
        tenant=tenant,
    )
    if request.method == "GET":
        return Response(ActivityRecordSerializer(record).data)
    if record.status == ActivityRecord.Status.LOCKED:
        return Response({"detail": "Locked audit records cannot be edited."}, status=status.HTTP_423_LOCKED)

    before = serialize_for_audit(record)
    editable_fields = {
        "scope",
        "category",
        "activity_date",
        "period_start",
        "period_end",
        "facility",
        "plant_code",
        "meter_id",
        "supplier",
        "vendor",
        "description",
        "canonical_quantity",
        "canonical_unit",
        "spend_amount",
        "currency",
        "analyst_notes",
    }
    for field in editable_fields:
        if field in request.data:
            if field == "facility":
                record.facility_id = request.data[field] or None
            elif field in {"activity_date", "period_start", "period_end"}:
                setattr(record, field, parse_date(request.data[field]))
            elif field in {"canonical_quantity", "spend_amount"}:
                setattr(record, field, parse_decimal(request.data[field]))
            else:
                setattr(record, field, request.data[field])
    record.edited_from_source = True
    record = recompute_record(record)
    record.save()
    AuditEvent.objects.create(
        tenant=tenant,
        activity_record=record,
        actor=actor_from(request),
        action="record_edited",
        before=before,
        after=serialize_for_audit(record),
        reason=request.data.get("reason", "Analyst edit"),
    )
    return Response(ActivityRecordSerializer(record).data)


def apply_record_action(record, action, actor, tenant, reason=""):
    before = serialize_for_audit(record)

    if action == "approve":
        if record.status == ActivityRecord.Status.LOCKED:
            return None, ("Record is already locked.", status.HTTP_409_CONFLICT)
        if record.status == ActivityRecord.Status.FAILED:
            return None, ("Fix failed rows before approval.", status.HTTP_400_BAD_REQUEST)
        if record.co2e_kg is None:
            return None, ("Record has no calculated emissions.", status.HTTP_400_BAD_REQUEST)
        record.status = ActivityRecord.Status.APPROVED
        record.approved_by = actor
        record.approved_at = timezone.now()
    elif action == "reject":
        if record.status == ActivityRecord.Status.LOCKED:
            return None, ("Locked audit records cannot be rejected.", status.HTTP_423_LOCKED)
        record.status = ActivityRecord.Status.REJECTED
    elif action == "lock":
        if record.status != ActivityRecord.Status.APPROVED:
            return None, ("Only approved records can be locked.", status.HTTP_400_BAD_REQUEST)
        record.status = ActivityRecord.Status.LOCKED
        record.locked_at = timezone.now()
    else:
        return None, ("Unsupported action.", status.HTTP_400_BAD_REQUEST)

    record.save()
    AuditEvent.objects.create(
        tenant=tenant,
        activity_record=record,
        actor=actor,
        action=f"record_{action}",
        before=before,
        after=serialize_for_audit(record),
        reason=reason,
    )
    return record, None


@api_view(["POST"])
def record_action(request, record_id, action):
    tenant = get_tenant(request)
    record = get_object_or_404(ActivityRecord, id=record_id, tenant=tenant)
    record, error = apply_record_action(record, action, actor_from(request), tenant, request.data.get("reason", ""))
    if error:
        detail, code = error
        return Response({"detail": detail}, status=code)
    return Response(ActivityRecordSerializer(record).data)


@api_view(["POST"])
def bulk_action(request):
    tenant = get_tenant(request)
    ids = request.data.get("ids", [])
    action = request.data.get("action")
    if not isinstance(ids, list) or action not in {"approve", "reject", "lock"}:
        return Response({"detail": "Provide ids[] and action approve/reject/lock."}, status=status.HTTP_400_BAD_REQUEST)
    updated = []
    errors = []
    for record in ActivityRecord.objects.filter(tenant=tenant, id__in=ids):
        updated_record, error = apply_record_action(
            record,
            action,
            actor_from(request),
            tenant,
            request.data.get("reason", "Bulk review"),
        )
        if error:
            errors.append({"id": record.id, "detail": error[0]})
        else:
            updated.append(ActivityRecordSerializer(updated_record).data)
    return Response({"updated": updated, "errors": errors})


@api_view(["GET"])
def audit_events(request):
    tenant = get_tenant(request)
    events = AuditEvent.objects.filter(tenant=tenant).select_related("activity_record", "batch")
    if request.query_params.get("record"):
        events = events.filter(activity_record_id=request.query_params["record"])
    return Response(AuditEventSerializer(events[:100], many=True).data)


@api_view(["POST"])
def reset_demo(request):
    tenant = ensure_demo_tenant()
    ActivityRecord.objects.filter(tenant=tenant).delete()
    IngestionBatch.objects.filter(tenant=tenant).delete()
    AuditEvent.objects.filter(tenant=tenant).delete()
    return Response({"tenant": TenantSerializer(tenant).data, "detail": "Demo records cleared; upload samples to reload."})


@api_view(["GET"])
def health(request):
    tenant_count = Tenant.objects.count()
    record_count = ActivityRecord.objects.count()
    return Response(
        {
            "status": "ok",
            "tenants": tenant_count,
            "records": record_count,
        }
    )


SAMPLE_FILES = {
    "sap": ("sap_material_procurement_export.csv", "text/csv"),
    "utility": ("utility_portal_greenbutton_like.csv", "text/csv"),
    "travel": ("concur_travel_export.json", "application/json"),
}


@api_view(["GET"])
def sample_manifest(request):
    return Response(
        {
            "samples": [
                {
                    "source_type": "sap",
                    "path": "sample_data/sap_material_procurement_export.csv",
                    "download_url": "/api/samples/sap/download/",
                    "description": "S/4HANA material document and purchase order CSV with mixed English/German headers.",
                },
                {
                    "source_type": "utility",
                    "path": "sample_data/utility_portal_greenbutton_like.csv",
                    "download_url": "/api/samples/utility/download/",
                    "description": "Utility portal CSV with billing periods, tariffs, meter ids, cost, demand, and estimates.",
                },
                {
                    "source_type": "travel",
                    "path": "sample_data/concur_travel_export.json",
                    "download_url": "/api/samples/travel/download/",
                    "description": "Concur-like travel segment export covering flights, hotel, ground transport, and personal expenses.",
                },
            ]
        }
    )


@api_view(["GET"])
def sample_download(request, source_type):
    if source_type not in SAMPLE_FILES:
        return Response({"detail": "Unknown sample type."}, status=status.HTTP_404_NOT_FOUND)
    filename, content_type = SAMPLE_FILES[source_type]
    path = Path(__file__).resolve().parents[1] / "sample_data" / filename
    if not path.exists():
        raise Http404("Sample file not found.")
    return FileResponse(path.open("rb"), as_attachment=True, filename=filename, content_type=content_type)
