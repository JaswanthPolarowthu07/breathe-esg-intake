from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path


def app_shell(request):
    return render(request, "index.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("ingest.urls")),
    path("", app_shell, name="app-shell"),
]
