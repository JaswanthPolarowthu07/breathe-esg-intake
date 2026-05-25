from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from ingest.models import ActivityRecord, SourceSystem
from ingest.services import ensure_demo_tenant, ingest_file


class Command(BaseCommand):
    help = "Create demo tenant, lookups, emission factors, and optionally ingest bundled sample files."

    def add_arguments(self, parser):
        parser.add_argument("--with-samples", action="store_true", help="Load bundled sample files.")
        parser.add_argument("--if-empty", action="store_true", help="Only load samples when no activity rows exist.")

    def handle(self, *args, **options):
        tenant = ensure_demo_tenant()
        self.stdout.write(self.style.SUCCESS(f"Demo tenant ready: {tenant.name}"))
        if not options["with_samples"] and not options["if_empty"]:
            return
        if options["if_empty"] and ActivityRecord.objects.filter(tenant=tenant).exists():
            self.stdout.write("Sample rows already exist; leaving them untouched.")
            return
        root = Path(__file__).resolve().parents[3]
        samples = [
            (SourceSystem.SourceType.SAP, root / "sample_data" / "sap_material_procurement_export.csv"),
            (SourceSystem.SourceType.UTILITY, root / "sample_data" / "utility_portal_greenbutton_like.csv"),
            (SourceSystem.SourceType.TRAVEL, root / "sample_data" / "concur_travel_export.json"),
        ]
        for source_type, path in samples:
            if not path.exists():
                self.stdout.write(self.style.WARNING(f"Missing sample file: {path}"))
                continue
            content = ContentFile(path.read_bytes(), name=path.name)
            batch = ingest_file(tenant, source_type, content, actor="Seed script")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Loaded {path.name}: {batch.normalized_rows} normalized, "
                    f"{batch.failed_rows} failed, {batch.suspicious_rows} suspicious"
                )
            )
