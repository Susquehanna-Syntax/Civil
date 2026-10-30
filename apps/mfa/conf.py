"""Civil settings read by the mfa app, with defaults.

``apps/mfa`` is copied into Mercantil and Jackil, so everything app-specific
arrives here rather than through an import of a Civil module.
"""

from importlib import import_module

from django.conf import settings


def _dotted(path):
    module_path, _, name = path.rpartition(".")
    return getattr(import_module(module_path), name)


def issuer() -> str:
    return getattr(settings, "MFA_ISSUER", "Civil")


def required_fn():
    path = getattr(settings, "MFA_REQUIRED", "apps.mfa.policy.everyone")
    if callable(path):
        return path
    return _dotted(path)


def required(user) -> bool:
    return bool(required_fn()(user))


def trusted_backends() -> tuple[str, ...]:
    return tuple(getattr(settings, "MFA_TRUSTED_BACKENDS", ()))
