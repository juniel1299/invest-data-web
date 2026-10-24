from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AccountViewSet, TransactionViewSet, summary

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="account")
router.register("transactions", TransactionViewSet, basename="transaction")

urlpatterns = [path("summary/", summary, name="portfolio-summary"), *router.urls]
