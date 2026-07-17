import time
from urllib.parse import parse_qs, urlparse

import jwt as pyjwt
from django.test import TestCase

from .models import Org, OrgMembership, RegisteredApp, SigningKeyRecord, User
from .tokens import issue_sso_token, verify_token


class KeyTests(TestCase):
    def test_key_generated_once_and_persisted(self):
        first = SigningKeyRecord.get()
        second = SigningKeyRecord.get()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SigningKeyRecord.objects.count(), 1)
        self.assertIn("BEGIN PUBLIC KEY", first.public_pem)


class TokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", email="a@example.com",
                                             password="x", first_name="Alice")
        org = Org.objects.create(name="Acme", slug="acme")
        OrgMembership.objects.create(user=self.user, org=org)

    def test_round_trip_carries_identity(self):
        claims = verify_token(issue_sso_token(self.user, "vigil"), "vigil")
        self.assertEqual(claims["sub"], str(self.user.id))
        self.assertEqual(claims["aud"], "vigil")
        self.assertEqual(claims["iss"], "civil")
        self.assertEqual(claims["orgs"][0]["slug"], "acme")

    def test_wrong_audience_rejected(self):
        token = issue_sso_token(self.user, "vigil")
        with self.assertRaises(pyjwt.InvalidAudienceError):
            verify_token(token, "jackil")

    def test_expired_token_rejected(self):
        token = issue_sso_token(self.user, "vigil")
        payload = pyjwt.decode(token, options={"verify_signature": False},
                               audience="vigil")
        self.assertLessEqual(payload["exp"] - time.time(), 60 + 1)
        # Simulate expiry by verifying with no leeway at a future time: craft
        # a token that is already expired instead of sleeping.
        expired = pyjwt.encode(
            {**payload, "iat": payload["iat"] - 3600, "exp": payload["iat"] - 3540},
            SigningKeyRecord.get().private_pem, algorithm="EdDSA",
        )
        with self.assertRaises(pyjwt.ExpiredSignatureError):
            verify_token(expired, "vigil")


class SsoAuthorizeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="x")
        self.app = RegisteredApp.objects.create(
            slug="vigil", name="Vigil",
            redirect_base="https://vigil.example.com/accounts/civil/callback",
        )
        self.client.force_login(self.user)

    def test_happy_path_redirects_with_token_and_state(self):
        resp = self.client.get("/sso/authorize", {
            "app": "vigil",
            "redirect_uri": "https://vigil.example.com/accounts/civil/callback",
            "state": "abc123",
        })
        self.assertEqual(resp.status_code, 302)
        q = parse_qs(urlparse(resp["Location"]).query)
        self.assertEqual(q["state"], ["abc123"])
        claims = verify_token(q["token"][0], "vigil")
        self.assertEqual(claims["sub"], str(self.user.id))
        self.assertEqual(resp["Cache-Control"], "no-store")

    def test_unknown_app_is_400(self):
        resp = self.client.get("/sso/authorize", {
            "app": "evil", "redirect_uri": "https://vigil.example.com/x"})
        self.assertEqual(resp.status_code, 400)

    def test_disabled_app_is_400(self):
        self.app.enabled = False
        self.app.save()
        resp = self.client.get("/sso/authorize", {
            "app": "vigil",
            "redirect_uri": "https://vigil.example.com/accounts/civil/callback"})
        self.assertEqual(resp.status_code, 400)

    def test_redirect_outside_allowlist_is_400(self):
        for bad in (
            "https://attacker.example.com/steal",
            "https://vigil.example.com.attacker.net/accounts/civil/callback",
            "http://vigil.example.com/accounts/civil/callback",  # scheme downgrade
        ):
            resp = self.client.get("/sso/authorize",
                                   {"app": "vigil", "redirect_uri": bad})
            self.assertEqual(resp.status_code, 400, bad)

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        resp = self.client.get("/sso/authorize", {
            "app": "vigil",
            "redirect_uri": "https://vigil.example.com/accounts/civil/callback"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])


class EndpointTests(TestCase):
    def test_pubkey_is_public_and_pem(self):
        resp = self.client.get("/api/v1/pubkey/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("BEGIN PUBLIC KEY", resp.json()["public_key_pem"])

    def test_whoami_requires_login(self):
        self.assertEqual(self.client.get("/api/v1/whoami/").status_code, 302)

    def test_health(self):
        self.assertEqual(self.client.get("/api/v1/health/").json()["status"], "ok")
