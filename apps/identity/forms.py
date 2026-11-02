"""Forms for the staff console. Each edits identity only: no roles, no
licenses, nothing a product owns (models.py)."""

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from .models import Org, RegisteredApp, Site, User


class PersonForm(forms.ModelForm):
    """A person and the organisations they belong to. The password is
    required for a new person and optional when editing (blank keeps it)."""

    password = forms.CharField(widget=forms.PasswordInput(render_value=False), required=False,
                               strip=False)
    orgs = forms.ModelMultipleChoiceField(queryset=Org.objects.order_by("name"), required=False,
                                          widget=forms.CheckboxSelectMultiple,
                                          label="Organisations")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active", "is_staff")
        labels = {"is_active": "Can sign in", "is_staff": "Civil staff"}
        help_texts = {
            "username": "Used to sign in to Civil.",
            "is_staff": "Can open this console. Roles in each app are set in that app.",
            "is_active": "Turn off to stop every new sign-in through Civil.",
        }

    def __init__(self, *args, can_grant_staff=False, editing_self=False, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        # Nobody locks themselves out of the console by mistake.
        if not can_grant_staff or editing_self:
            del self.fields["is_staff"]
        if editing_self:
            del self.fields["is_active"]
        # UUID keys exist before the first save, so pk cannot tell new from old.
        if not self.instance._state.adding:
            self.initial["orgs"] = list(self.instance.memberships.values_list("org_id", flat=True))
            self.fields["password"].help_text = "Leave blank to keep the current password."
        else:
            self.fields["password"].required = True

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            validate_password(password, self.instance)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        user.save()
        wanted = set(self.cleaned_data["orgs"])
        user.memberships.exclude(org__in=wanted).delete()
        have = set(user.memberships.values_list("org_id", flat=True))
        for org in wanted:
            if org.id not in have:
                user.memberships.create(org=org)
        return user


class AppForm(forms.ModelForm):
    class Meta:
        model = RegisteredApp
        fields = ("name", "slug", "redirect_base", "enabled")
        labels = {"redirect_base": "Callback address", "enabled": "Sign-ins allowed"}
        help_texts = {
            "slug": "The app's Civil setting names it, e.g. vigil.",
            "redirect_base": "Civil sends sign-in tokens only to addresses under this one, "
                             "e.g. https://vigil.example.com/accounts/civil/callback",
        }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    def clean_redirect_base(self):
        url = self.cleaned_data["redirect_base"]
        if not url.lower().startswith(("https://", "http://")):
            raise forms.ValidationError("Use an http:// or https:// address.")
        return url


class OrgForm(forms.ModelForm):
    class Meta:
        model = Org
        fields = ("name", "slug")
        help_texts = {"slug": "Leave blank to make one from the name."}

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))
        if not slug:
            raise forms.ValidationError("Give it a name or a slug.")
        if Org.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another organisation already uses this slug.")
        return slug


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ("name", "slug")

    def __init__(self, *args, org=None, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.org = org
        self.fields["slug"].required = False

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))
        if not slug:
            raise forms.ValidationError("Give it a name or a slug.")
        if Site.objects.filter(org=self.org, slug=slug).exists():
            raise forms.ValidationError("This organisation already has a site with that slug.")
        return slug

    def save(self, commit=True):
        site = super().save(commit=False)
        site.org = self.org
        site.save()
        return site
