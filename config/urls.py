from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Custom admin header and title
admin.site.site_header = "PUBG MOBILE UC SHOP - Boshqaruv Paneli"
admin.site.site_title = "PUBG UC Bot Admin"
admin.site.index_title = "Asosiy boshqaruv paneli va statistika"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/webhooks/", include("apps.payments.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
