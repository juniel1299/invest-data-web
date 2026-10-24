from django.urls import path

from . import views

urlpatterns = [
    path("people/", views.people),
    path("people/<slug:slug>/", views.person_detail),
    path("people/<slug:slug>/follow/", views.follow),
    path("feed/", views.feed),
    path("notifications/", views.notifications),
    path("notifications/read/", views.read_notifications),
    path("principles/", views.principles_view),
]
