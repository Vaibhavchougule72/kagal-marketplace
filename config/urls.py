from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import path, include
from django.contrib import admin

def assetlinks(request):
    return JsonResponse([
        {
            "relation": [
                "delegate_permission/common.handle_all_urls"
            ],
            "target": {
                "namespace": "android_app",
                "package_name": "com.lokamarketplace.app",
                "sha256_cert_fingerprints": [
                    "A7:71:D1:42:6F:E9:03:20:2F:0E:4A:A6:DF:E5:73:37:C2:B7:8B:97:99:2D:F0:CF:E1:24:65:9F:BC:F1:34:6E"
                ]
            }
        }
    ], safe=False)

urlpatterns = [
    path('admin/', admin.site.urls),

    path(
        '.well-known/assetlinks.json',
        assetlinks
    ),

    path('', include('marketplace.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )