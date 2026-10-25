from django.urls import path

from . import views

urlpatterns = [
    path("", views.summaries),
    path("<str:day>/", views.summary_detail),
]
