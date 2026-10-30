from django.urls import path

from . import views

app_name = "mfa"

urlpatterns = [
    path("verify/", views.verify, name="verify"),
    path("codes/", views.codes, name="codes"),
    path("", views.security, name="security"),
    path("setup/", views.setup, name="setup"),
]
