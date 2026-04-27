from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.templatetags.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path(
        '.well-known/assetlinks.json',
        RedirectView.as_view(
            url=static('.well-known/assetlinks.json'),
            permanent=False
        )
    ),

    path('', include('marketplace.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
