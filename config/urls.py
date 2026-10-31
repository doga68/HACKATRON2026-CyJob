from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("personel/", include("jobs.urls")),   # iş arayan portalı  -> /personel/
    path("isveren/", include("core.urls")),    # işveren portalı    -> /isveren/
    path("", include("portal.urls")),          # ana sayfa          -> /
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
