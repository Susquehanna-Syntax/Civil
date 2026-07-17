from django.apps import AppConfig


class IdentityConfig(AppConfig):
    name = "apps.identity"
    verbose_name = "Identity"
    # No ready() work: the signing key is generated lazily on first use so
    # migrations and management commands never trip over it.
