from django.urls import reverse
from rest_framework.test import APITestCase


class AuthFlowTests(APITestCase):
    def test_register_login_and_me(self):
        res = self.client.post(
            reverse("register"),
            {"email": "me@example.com", "password": "s3cure-pass-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertNotIn("password", res.data)

        res = self.client.post(
            reverse("token"),
            {"email": "me@example.com", "password": "s3cure-pass-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        access = res.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        res = self.client.get(reverse("me"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["email"], "me@example.com")
        self.assertEqual(res.data["display_currency"], "KRW")

    def test_weak_password_rejected(self):
        res = self.client.post(
            reverse("register"), {"email": "a@example.com", "password": "1234"}, format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_me_requires_login(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)
