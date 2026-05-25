from django.contrib import admin

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


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "default_currency", "created_at")
    search_fields = ("name", "slug")


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("tenant", "code", "name", "country", "region")
    list_filter = ("tenant", "country")
    search_fields = ("code", "name")


@admin.register(PlantLookup)
class PlantLookupAdmin(admin.ModelAdmin):
    list_display = ("tenant", "plant_code", "facility", "active")
    list_filter = ("tenant", "active")
    search_fields = ("plant_code", "facility__name")


@admin.register(SourceSystem)
class SourceSystemAdmin(admin.ModelAdmin):
    list_display = ("tenant", "source_type", "name", "ingestion_mode", "owner")
    list_filter = ("tenant", "source_type")
    search_fields = ("name", "owner")


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = ("tenant", "key", "unit", "kg_co2e_per_unit", "source")
    list_filter = ("tenant", "unit")
    search_fields = ("key", "label", "source")


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "source_system",
        "filename",
        "status",
        "total_rows",
        "normalized_rows",
        "failed_rows",
        "suspicious_rows",
        "created_at",
    )
    list_filter = ("tenant", "status", "source_system__source_type")
    search_fields = ("filename",)


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ("batch", "row_number", "parse_status", "row_hash", "created_at")
    list_filter = ("parse_status",)
    search_fields = ("row_hash",)


@admin.register(ActivityRecord)
class ActivityRecordAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "source_system",
        "source_record_key",
        "scope",
        "category",
        "status",
        "canonical_quantity",
        "canonical_unit",
        "co2e_kg",
    )
    list_filter = ("tenant", "scope", "category", "status", "source_system__source_type")
    search_fields = ("source_record_key", "description", "vendor", "supplier")
    readonly_fields = ("raw_fingerprint",)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("tenant", "action", "actor", "activity_record", "batch", "created_at")
    list_filter = ("tenant", "action")
    search_fields = ("actor", "reason")
