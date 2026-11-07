from django.contrib import admin
from django.urls import path, re_path
from django.views.generic.base import RedirectView
from urza_core.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    # Si alguien llama directamente con el prefijo /api/ (ej. cURL o pruebas sin Vite),
    # se redirige internamente a la ruta base de Ninja.
    re_path(r"^api/(?P<path>.*)$", RedirectView.as_view(url="/%(path)s", permanent=False, query_string=True)),
    path("", api.urls),
]
