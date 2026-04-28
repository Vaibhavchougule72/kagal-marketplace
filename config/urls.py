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
                    "58:C3:B6:8D:35:D8:AE:C4:AF:43:FE:DF:57:69:77:DB:2F:DC:26:15:4A:CC:09:AE:AE:EA:A0:BD:8F:40:02:5D"
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