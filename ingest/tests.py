from decimal import Decimal
from pathlib import Path

from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework.test import APIClient

from .models import ActivityRecord
from .services import ensure_demo_tenant, ingest_file, parse_date, parse_decimal


ROOT = Path(__file__).resolve().parents[1]


def sample_file(name):
    path = ROOT / "sample_data" / name
    return ContentFile(path.read_bytes(), name=name)


class NormalizationTests(TestCase):
    def setUp(self):
        self.tenant = ensure_demo_tenant()

    def test_parses_realistic_decimal_and_date_variants(self):
        self.assertEqual(parse_decimal("1.234,56"), parse_decimal("1234.56"))
        self.assertEqual(parse_date("31.03.2025").isoformat(), "2025-03-31")
        self.assertEqual(parse_date("/Date(1743379200000)/").isoformat(), "2025-03-31")

    def test_sap_sample_normalizes_fuel_procurement_and_flags_edges(self):
        batch = ingest_file(
            self.tenant,
            "sap",
            sample_file("sap_material_procurement_export.csv"),
            actor="Test Analyst",
        )
        self.assertEqual(batch.total_rows, 6)
        self.assertEqual(batch.failed_rows, 0)
        gallons = ActivityRecord.objects.get(source_record_key="MATDOC:4900001101:2025:1")
        self.assertIn("unit_converted_gal_to_l", gallons.quality_flags)
        self.assertIn("unknown_plant_code", gallons.quality_flags)
        eur_procurement = ActivityRecord.objects.get(source_record_key="PO:4500107799:20")
        self.assertIn("non_usd_spend_no_fx", eur_procurement.quality_flags)

    def test_utility_sample_tracks_billing_period_and_failed_rows(self):
        batch = ingest_file(
            self.tenant,
            "utility",
            sample_file("utility_portal_greenbutton_like.csv"),
            actor="Test Analyst",
        )
        self.assertEqual(batch.failed_rows, 2)
        duplicate = ActivityRecord.objects.get(source_record_key__contains="INV-88421-R1")
        self.assertIn("duplicate_meter_period", duplicate.quality_flags)

    def test_travel_sample_estimates_airport_distance_and_excludes_personal(self):
        batch = ingest_file(
            self.tenant,
            "travel",
            sample_file("concur_travel_export.json"),
            actor="Test Analyst",
        )
        self.assertEqual(batch.failed_rows, 2)
        flight = ActivityRecord.objects.get(source_record_key="TRAVEL:TR-8801:AIR-1")
        self.assertIn("distance_estimated_from_airports", flight.quality_flags)
        personal = ActivityRecord.objects.get(source_record_key="TRAVEL:TR-8818:AIR-PERSONAL")
        self.assertEqual(personal.status, ActivityRecord.Status.FAILED)


class ReviewWorkflowTests(TestCase):
    def setUp(self):
        self.tenant = ensure_demo_tenant()
        ingest_file(
            self.tenant,
            "travel",
            sample_file("concur_travel_export.json"),
            actor="Test Analyst",
        )
        self.client = APIClient()

    def test_approve_then_lock_writes_audit_and_blocks_locked_edit(self):
        record = ActivityRecord.objects.filter(status=ActivityRecord.Status.NEEDS_REVIEW, co2e_kg__isnull=False).first()
        approve = self.client.post(
            f"/api/records/{record.id}/approve/",
            {"tenant": self.tenant.id, "actor": "Jaswanth Analyst"},
            format="json",
        )
        self.assertEqual(approve.status_code, 200)
        lock = self.client.post(
            f"/api/records/{record.id}/lock/",
            {"tenant": self.tenant.id, "actor": "Nina Auditor"},
            format="json",
        )
        self.assertEqual(lock.status_code, 200)
        edit = self.client.patch(
            f"/api/records/{record.id}/",
            {"tenant": self.tenant.id, "canonical_quantity": "1"},
            format="json",
        )
        self.assertEqual(edit.status_code, 423)

    def test_record_detail_save_accepts_string_decimal_and_date_inputs(self):
        record = ActivityRecord.objects.filter(status=ActivityRecord.Status.NEEDS_REVIEW, co2e_kg__isnull=False).first()
        response = self.client.patch(
            f"/api/records/{record.id}/",
            {
                "tenant": self.tenant.id,
                "actor": "Jaswanth Analyst",
                "description": "Updated by test",
                "canonical_quantity": "2.5",
                "spend_amount": "1234.56",
                "activity_date": "2025-03-31",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.description, "Updated by test")
        self.assertEqual(record.canonical_quantity, Decimal("2.5"))
        self.assertEqual(record.spend_amount, Decimal("1234.56"))
        self.assertEqual(record.activity_date.isoformat(), "2025-03-31")
