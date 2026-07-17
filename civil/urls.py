from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.urls import path

from apps.identity import views as identity


def health(request):
    return JsonResponse({"status": "ok", "service": "civil"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("sso/authorize", identity.authorize, name="sso-authorize"),
    path("api/v1/pubkey/", identity.pubkey, name="pubkey"),
    path("api/v1/whoami/", identity.whoami, name="whoami"),
    path("api/v1/health/", health, name="health"),
    path("", identity.whoami, name="index"),
]
