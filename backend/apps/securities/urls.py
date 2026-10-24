from django.urls import path

from apps.market.views import security_detail, security_prices

from .views import SecuritySearchView

urlpatterns = [
    path("", SecuritySearchView.as_view(), name="security-search"),
    path("<str:ticker>/", security_detail, name="security-detail"),
    path("<str:ticker>/prices/", security_prices, name="security-prices"),
]
