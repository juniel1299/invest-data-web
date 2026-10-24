from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.securities.models import Security


class SecuritySearchTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("me@example.com", "s3cure-pass-123")
        self.client.force_authenticate(user)
        Security.objects.create(ticker="AAPL", name="Apple Inc.", name_ko="애플", exchange="Nasdaq")
        Security.objects.create(ticker="AA", name="Alcoa Corp", exchange="NYSE")
        Security.objects.create(ticker="APLE", name="Apple Hospitality REIT", exchange="NYSE")
        Security.objects.create(ticker="OLD", name="Apple Delisted", exchange="NYSE", is_active=False)

    def search(self, q):
        res = self.client.get(reverse("security-search"), {"q": q})
        self.assertEqual(res.status_code, 200)
        return [r["ticker"] for r in res.data]

    def test_exact_ticker_first(self):
        self.assertEqual(self.search("aa")[0], "AA")

    def test_name_and_korean_name(self):
        self.assertEqual(self.search("apple"), ["AAPL", "APLE"])
        self.assertEqual(self.search("애플"), ["AAPL"])

    def test_empty_query(self):
        self.assertEqual(self.search(""), [])
