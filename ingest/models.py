from django.conf import settings
from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    default_currency = models.CharField(max_length=3, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Facility(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="facilities")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    country = models.CharField(max_length=2, default="US")
    region = models.CharField(max_length=80, blank=True)
    meter_aliases = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = [("tenant", "code")]
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class PlantLookup(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="plant_lookups")
    plant_code = models.CharField(max_length=40)
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="plant_codes")
    label = models.CharField(max_length=160, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("tenant", "plant_code")]
        ordering = ["plant_code"]

    def __str__(self):
        return f"{self.plant_code} -> {self.facility.code}"


class SourceSystem(models.Model):
    class SourceType(models.TextChoices):
        SAP = "sap", "SAP"
        UTILITY = "utility", "Utility"
        TRAVEL = "travel", "Travel"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="source_systems")
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    name = models.CharField(max_length=160)
    ingestion_mode = models.CharField(max_length=80)
    owner = models.CharField(max_length=160, blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("tenant", "source_type", "name")]
        ordering = ["source_type", "name"]

    def __str__(self):
        return f"{self.get_source_type_display()} - {self.name}"


class EmissionFactor(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="emission_factors",
        null=True,
        blank=True,
    )
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=160)
    unit = models.CharField(max_length=32)
    kg_co2e_per_unit = models.DecimalField(max_digits=14, decimal_places=6)
    source = models.CharField(max_length=240)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("tenant", "key", "unit")]
        ordering = ["key", "unit"]

    def __str__(self):
        return f"{self.key} ({self.unit})"


class IngestionBatch(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="batches")
    source_system = models.ForeignKey(SourceSystem, on_delete=models.PROTECT, related_name="batches")
    filename = models.CharField(max_length=240)
    uploaded_by = models.CharField(max_length=160, default="Demo Analyst")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING)
    total_rows = models.PositiveIntegerField(default=0)
    normalized_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    suspicious_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    schema_version = models.CharField(max_length=40, default="prototype-v1")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source_system} - {self.filename}"


class RawRecord(models.Model):
    class ParseStatus(models.TextChoices):
        NORMALIZED = "normalized", "Normalized"
        FAILED = "failed", "Failed"
        DUPLICATE = "duplicate", "Duplicate"

    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name="raw_records")
    row_number = models.PositiveIntegerField()
    raw_data = models.JSONField(default=dict)
    row_hash = models.CharField(max_length=64, db_index=True)
    parse_status = models.CharField(max_length=16, choices=ParseStatus.choices)
    errors = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("batch", "row_number")]
        ordering = ["batch_id", "row_number"]

    def __str__(self):
        return f"{self.batch_id}:{self.row_number}"


class ActivityRecord(models.Model):
    class Scope(models.TextChoices):
        SCOPE_1 = "scope_1", "Scope 1"
        SCOPE_2 = "scope_2", "Scope 2"
        SCOPE_3 = "scope_3", "Scope 3"

    class Status(models.TextChoices):
        NEEDS_REVIEW = "needs_review", "Needs review"
        FAILED = "failed", "Failed"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        LOCKED = "locked", "Locked for audit"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="activity_records")
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name="activity_records")
    raw_record = models.OneToOneField(
        RawRecord,
        on_delete=models.PROTECT,
        related_name="activity_record",
        null=True,
        blank=True,
    )
    source_system = models.ForeignKey(SourceSystem, on_delete=models.PROTECT, related_name="activity_records")
    source_record_key = models.CharField(max_length=180, db_index=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    raw_fingerprint = models.CharField(max_length=64, db_index=True)

    scope = models.CharField(max_length=16, choices=Scope.choices)
    category = models.CharField(max_length=80)
    activity_date = models.DateField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        related_name="activity_records",
        null=True,
        blank=True,
    )
    plant_code = models.CharField(max_length=40, blank=True)
    meter_id = models.CharField(max_length=80, blank=True)
    supplier = models.CharField(max_length=160, blank=True)
    vendor = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)

    original_quantity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    original_unit = models.CharField(max_length=32, blank=True)
    canonical_quantity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    canonical_unit = models.CharField(max_length=32, blank=True)
    spend_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    emission_factor = models.ForeignKey(
        EmissionFactor,
        on_delete=models.PROTECT,
        related_name="activity_records",
        null=True,
        blank=True,
    )
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEEDS_REVIEW)
    quality_flags = models.JSONField(default=list, blank=True)
    normalized_payload = models.JSONField(default=dict, blank=True)
    analyst_notes = models.TextField(blank=True)
    edited_from_source = models.BooleanField(default=False)
    approved_by = models.CharField(max_length=160, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "source_system", "source_record_key", "raw_fingerprint")]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "scope"]),
            models.Index(fields=["tenant", "category"]),
        ]

    def __str__(self):
        return f"{self.source_system.source_type}:{self.source_record_key}"


class AuditEvent(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_events")
    activity_record = models.ForeignKey(
        ActivityRecord,
        on_delete=models.CASCADE,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.CASCADE,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    actor = models.CharField(max_length=160, default="System")
    action = models.CharField(max_length=80)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} by {self.actor}"
