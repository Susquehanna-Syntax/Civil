from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Org, OrgMembership, RegisteredApp, Site, User

admin.site.register(User, UserAdmin)


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "org", "slug", "created_at")
    list_filter = ("org",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(OrgMembership)
class OrgMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "org", "created_at")
    list_filter = ("org",)


@admin.register(RegisteredApp)
class RegisteredAppAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "redirect_base", "enabled")
