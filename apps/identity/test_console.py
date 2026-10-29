from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import Org, OrgMembership, RegisteredApp, Site, User

STRONG = "correct-horse-battery-9"


def staff(username="staffer", *codenames):
    user = User.objects.create_user(username, password=STRONG, is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    return user


class HomeTests(TestCase):
    def test_home_needs_sign_in(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("/login/"))

    def test_home_lists_enabled_apps_by_their_origin(self):
        RegisteredApp.objects.create(slug="vigil", name="Vigil",
                                     redirect_base="https://vigil.example.com/accounts/civil/callback")
        RegisteredApp.objects.create(slug="old", name="Retired", enabled=False,
                                     redirect_base="https://old.example.com/cb")
        self.client.force_login(User.objects.create_user("alice", password=STRONG))
        resp = self.client.get("/")
        self.assertContains(resp, 'href="https://vigil.example.com/"')
        self.assertNotContains(resp, "Retired")
        self.assertNotContains(resp, "/console/people/")

    def test_whoami_still_answers_json(self):
        self.client.force_login(User.objects.create_user("alice", password=STRONG))
        self.assertEqual(self.client.get("/api/v1/whoami/").json()["username"], "alice")

    def test_change_password(self):
        user = User.objects.create_user("alice", password=STRONG)
        self.client.force_login(user)
        self.client.post(reverse("password"), {"old_password": STRONG,
                                               "new_password1": "another-long-pass-4",
                                               "new_password2": "another-long-pass-4"})
        user.refresh_from_db()
        self.assertTrue(user.check_password("another-long-pass-4"))


class AccessTests(TestCase):
    def test_a_person_who_is_not_staff_gets_403(self):
        self.client.force_login(User.objects.create_user("alice", password=STRONG))
        self.assertEqual(self.client.get(reverse("console-people")).status_code, 403)

    def test_staff_without_permissions_cannot_read(self):
        self.client.force_login(staff())
        for name in ("console-people", "console-apps", "console-orgs"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_view_only_staff_can_read_but_not_add(self):
        self.client.force_login(staff("viewer", "view_user", "view_registeredapp"))
        self.assertEqual(self.client.get(reverse("console-people")).status_code, 200)
        self.assertEqual(self.client.get(reverse("console-person-new")).status_code, 403)
        app = RegisteredApp.objects.create(slug="vigil", name="Vigil", redirect_base="https://v/cb")
        self.assertEqual(self.client.post(reverse("console-app-toggle", args=[app.pk])).status_code, 403)

    def test_only_a_superuser_edits_a_superuser(self):
        boss = User.objects.create_superuser("boss", password=STRONG)
        self.client.force_login(staff("helper", "change_user", "view_user"))
        resp = self.client.post(reverse("console-person", args=[boss.pk]),
                                {"username": "boss", "password": "taken-over-pass-1"})
        self.assertEqual(resp.status_code, 403)
        boss.refresh_from_db()
        self.assertTrue(boss.check_password(STRONG))

    def test_only_a_superuser_can_grant_staff(self):
        self.client.force_login(staff("helper", "add_user"))
        self.client.post(reverse("console-person-new"), {
            "username": "newbie", "password": STRONG, "is_active": "on", "is_staff": "on"})
        self.assertFalse(User.objects.get(username="newbie").is_staff)


class PeopleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password=STRONG)
        self.client.force_login(self.admin)
        self.org = Org.objects.create(name="Acme", slug="acme")

    def test_add_a_person_with_a_password_and_an_org(self):
        resp = self.client.post(reverse("console-person-new"), {
            "username": "tom", "first_name": "Tom", "email": "tom@example.com",
            "password": STRONG, "is_active": "on", "orgs": [str(self.org.pk)]})
        self.assertRedirects(resp, reverse("console-people"))
        tom = User.objects.get(username="tom")
        self.assertTrue(tom.check_password(STRONG))
        self.assertTrue(OrgMembership.objects.filter(user=tom, org=self.org).exists())
        self.assertTrue(LogEntry.objects.filter(object_id=str(tom.pk)).exists())

    def test_a_new_person_needs_a_password_and_a_weak_one_is_refused(self):
        self.client.post(reverse("console-person-new"), {"username": "tom", "is_active": "on"})
        resp = self.client.post(reverse("console-person-new"), {
            "username": "tom", "password": "123", "is_active": "on"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="tom").exists())

    def test_editing_with_a_blank_password_keeps_it_and_orgs_follow_the_boxes(self):
        tom = User.objects.create_user("tom", password=STRONG)
        OrgMembership.objects.create(user=tom, org=self.org)
        other = Org.objects.create(name="Globex", slug="globex")
        self.client.post(reverse("console-person", args=[tom.pk]), {
            "username": "tom", "email": "t@x.example", "password": "", "is_active": "on",
            "orgs": [str(other.pk)]})
        tom.refresh_from_db()
        self.assertTrue(tom.check_password(STRONG))
        self.assertEqual(list(tom.memberships.values_list("org__slug", flat=True)), ["globex"])

    def test_editing_yourself_cannot_switch_off_your_own_access(self):
        self.client.post(reverse("console-person", args=[self.admin.pk]), {
            "username": "admin", "password": ""})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertTrue(self.admin.is_staff)

    def test_changing_your_own_password_keeps_you_signed_in(self):
        self.client.post(reverse("console-person", args=[self.admin.pk]), {
            "username": "admin", "password": "brand-new-pass-77"})
        self.assertEqual(self.client.get(reverse("console-people")).status_code, 200)

    def test_search(self):
        User.objects.create_user("priya", email="priya@example.com", password=STRONG)
        resp = self.client.get(reverse("console-people"), {"q": "priya@"})
        self.assertContains(resp, "priya")
        self.assertNotContains(resp, "<strong>admin</strong>")


class AppAndOrgTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", password=STRONG))

    def test_add_an_app_and_stop_its_sign_ins(self):
        self.client.post(reverse("console-app-new"), {
            "name": "Jackil", "slug": "jackil", "enabled": "on",
            "redirect_base": "https://jackil.example.com/accounts/civil/callback"})
        app = RegisteredApp.objects.get(slug="jackil")
        self.assertTrue(app.enabled)
        self.client.post(reverse("console-app-toggle", args=[app.pk]))
        app.refresh_from_db()
        self.assertFalse(app.enabled)

    def test_an_app_callback_must_be_http(self):
        resp = self.client.post(reverse("console-app-new"), {
            "name": "Bad", "slug": "bad", "redirect_base": "ftp://bad.example.com/cb"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(RegisteredApp.objects.exists())

    def test_toggle_needs_post(self):
        app = RegisteredApp.objects.create(slug="vigil", name="Vigil", redirect_base="https://v/cb")
        self.assertEqual(self.client.get(reverse("console-app-toggle", args=[app.pk])).status_code, 405)

    def test_add_an_org_with_a_slug_from_its_name(self):
        resp = self.client.post(reverse("console-org-new"), {"name": "HK Kolmar", "slug": ""})
        org = Org.objects.get()
        self.assertEqual(org.slug, "hk-kolmar")
        self.assertRedirects(resp, reverse("console-org", args=[org.pk]))

    def test_a_duplicate_org_slug_is_refused(self):
        Org.objects.create(name="Acme", slug="acme")
        resp = self.client.post(reverse("console-org-new"), {"name": "Acme Two", "slug": "acme"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Org.objects.count(), 1)

    def test_sites_and_members_on_the_org_page(self):
        org = Org.objects.create(name="Acme", slug="acme")
        tom = User.objects.create_user("tom", password=STRONG)
        self.client.post(reverse("console-org", args=[org.pk]), {"name": "Main Campus", "slug": ""})
        site = Site.objects.get(org=org)
        self.assertEqual(site.slug, "main-campus")
        self.client.post(reverse("console-member-add", args=[org.pk]), {"user": str(tom.pk)})
        self.assertTrue(OrgMembership.objects.filter(org=org, user=tom).exists())
        resp = self.client.get(reverse("console-org", args=[org.pk]))
        self.assertContains(resp, "Main Campus")
        self.assertContains(resp, "tom")
        self.client.post(reverse("console-member-remove", args=[org.pk, tom.pk]))
        self.client.post(reverse("console-site-delete", args=[org.pk, site.pk]))
        self.assertFalse(OrgMembership.objects.filter(org=org).exists())
        self.assertFalse(Site.objects.exists())

    def test_a_duplicate_site_slug_in_one_org_is_refused(self):
        org = Org.objects.create(name="Acme", slug="acme")
        Site.objects.create(org=org, name="Lab", slug="lab")
        self.client.post(reverse("console-org", args=[org.pk]), {"name": "Lab", "slug": "lab"})
        self.assertEqual(Site.objects.count(), 1)

    def test_adding_a_bad_member_id_is_404(self):
        org = Org.objects.create(name="Acme", slug="acme")
        resp = self.client.post(reverse("console-member-add", args=[org.pk]), {"user": "nope"})
        self.assertEqual(resp.status_code, 404)
