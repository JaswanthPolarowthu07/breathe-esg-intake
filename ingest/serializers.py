from rest_framework import serializers

from .models import (
    ActivityRecord,
    AuditEvent,
    Facility,
    IngestionBatch,
    RawRecord,
    SourceSystem,
    Tenant,
)


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "default_currency"]


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ["id", "code", "name", "country", "region", "meter_aliases"]


class SourceSystemSerializer(serializers.ModelSerializer):
    source_type_label = serializers.CharField(source="get_source_type_display", read_only=True)

    class Meta:
        model = SourceSystem
        fields = ["id", "source_type", "source_type_label", "name", "ingestion_mode", "owner", "config"]


class BatchSerializer(serializers.ModelSerializer):
    source_type = serializers.CharField(source="source_system.source_type", read_only=True)
    source_name = serializers.CharField(source="source_system.name", read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            "id",
            "source_type",
            "source_name",
            "filename",
            "uploaded_by",
            "status",
            "total_rows",
            "normalized_rows",
            "failed_rows",
            "suspicious_rows",
            "duplicate_rows",
            "schema_version",
            "notes",
            "created_at",
            "completed_at",
        ]


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ["id", "row_number", "raw_data", "row_hash", "parse_status", "errors", "warnings"]


class ActivityRecordSerializer(serializers.ModelSerializer):
    source_type = serializers.CharField(source="source_system.source_type", read_only=True)
    source_name = serializers.CharField(source="source_system.name", read_only=True)
    scope_label = serializers.CharField(source="get_scope_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    facility_code = serializers.CharField(source="facility.code", read_only=True, allow_null=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True, allow_null=True)
    emission_factor_label = serializers.CharField(source="emission_factor.label", read_only=True, allow_null=True)
    emission_factor_value = serializers.DecimalField(
        source="emission_factor.kg_co2e_per_unit",
        max_digits=14,
        decimal_places=6,
        read_only=True,
        allow_null=True,
    )
    raw_record = RawRecordSerializer(read_only=True)

    class Meta:
        model = ActivityRecord
        fields = [
            "id",
            "source_type",
            "source_name",
            "source_record_key",
            "scope",
            "scope_label",
            "category",
            "activity_date",
            "period_start",
            "period_end",
            "facility",
            "facility_code",
            "facility_name",
            "plant_code",
            "meter_id",
            "supplier",
            "vendor",
            "description",
            "original_quantity",
            "original_unit",
            "canonical_quantity",
            "canonical_unit",
            "spend_amount",
            "currency",
            "emission_factor",
            "emission_factor_label",
            "emission_factor_value",
            "co2e_kg",
            "status",
            "status_label",
            "quality_flags",
            "normalized_payload",
            "analyst_notes",
            "edited_from_source",
            "approved_by",
            "approved_at",
            "locked_at",
            "raw_record",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "source_type",
            "source_name",
            "source_record_key",
            "scope_label",
            "status_label",
            "facility_code",
            "facility_name",
            "original_quantity",
            "original_unit",
            "emission_factor_label",
            "emission_factor_value",
            "co2e_kg",
            "edited_from_source",
            "approved_by",
            "approved_at",
            "locked_at",
            "raw_record",
            "created_at",
            "updated_at",
        ]


class AuditEventSerializer(serializers.ModelSerializer):
    activity_source_key = serializers.CharField(source="activity_record.source_record_key", read_only=True)
    batch_filename = serializers.CharField(source="batch.filename", read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "activity_record",
            "activity_source_key",
            "batch",
            "batch_filename",
            "actor",
            "action",
            "before",
            "after",
            "reason",
            "created_at",
        ]
