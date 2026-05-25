from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("tenants/", views.tenants),
    path("facilities/", views.facilities),
    path("source-systems/", views.source_systems),
    path("overview/", views.overview),
    path("batches/", views.batches),
    path("records/", views.records),
    path("records/<int:record_id>/", views.record_detail),
    path("records/<int:record_id>/<str:action>/", views.record_action),
    path("records/bulk-action/", views.bulk_action),
    path("audit/", views.audit_events),
    path("ingest/<str:source_type>/", views.ingest),
    path("demo/reset/", views.reset_demo),
    path("samples/", views.sample_manifest),
    path("samples/<str:source_type>/download/", views.sample_download),
]
