from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.overview, name="market-overview"),
    path("news/", views.news, name="market-news"),
    path("calendar/", views.calendar, name="market-calendar"),
]
