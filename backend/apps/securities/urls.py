from django.urls import path

from .views import SecuritySearchView

urlpatterns = [
    path("", SecuritySearchView.as_view(), name="security-search"),
]
