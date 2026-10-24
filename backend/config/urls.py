from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/securities/", include("apps.securities.urls")),
    path("api/portfolio/", include("apps.portfolio.urls")),
    path("api/market/", include("apps.market.urls")),
]
