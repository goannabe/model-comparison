from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("models/", views.models),
    path("predict/", views.predict),
    path("predict/explain/", views.predict_explain),
    path("predict/batch/", views.predict_batch),
]
