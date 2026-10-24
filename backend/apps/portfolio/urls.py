from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AccountViewSet, TransactionViewSet, summary, unwatch, watches

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="account")
router.register("transactions", TransactionViewSet, basename="transaction")

urlpatterns = [
    path("summary/", summary, name="portfolio-summary"),
    path("watches/", watches, name="watches"),
    path("watches/<str:ticker>/", unwatch, name="unwatch"),
    *router.urls,
]
