import httpx
from django.test import TestCase

from apps.securities.models import Security
from apps.securities.services import sync_securities


def make_client(data):
    payload = {"fields": ["cik", "name", "ticker", "exchange"], "data": data}

    def handler(request):
        assert "User-Agent" in request.headers
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


class SyncSecuritiesTests(TestCase):
    def test_creates_supported_exchanges_only(self):
        result = sync_securities(
            make_client(
                [
                    [320193, "Apple Inc.", "AAPL", "Nasdaq"],
                    [70858, "Bank of America Corp", "BAC", "NYSE"],
                    [1, "Some Pink Sheet Co", "PINKX", "OTC"],
                    [2, "No Exchange Co", "NOEX", None],
                ]
            )
        )
        self.assertEqual(result.created, 2)
        self.assertEqual(set(Security.objects.values_list("ticker", flat=True)), {"AAPL", "BAC"})

    def test_updates_and_deactivates(self):
        Security.objects.create(ticker="AAPL", name="Old Name", exchange="Nasdaq", cik=320193)
        Security.objects.create(ticker="GONE", name="Delisted Co", exchange="NYSE", cik=9)

        result = sync_securities(make_client([[320193, "Apple Inc.", "AAPL", "Nasdaq"]]))

        self.assertEqual((result.created, result.updated, result.deactivated), (0, 1, 1))
        self.assertEqual(Security.objects.get(ticker="AAPL").name, "Apple Inc.")
        self.assertFalse(Security.objects.get(ticker="GONE").is_active)

    def test_keeps_korean_name_on_update(self):
        Security.objects.create(ticker="AAPL", name="Old", name_ko="애플", exchange="Nasdaq")
        sync_securities(make_client([[320193, "Apple Inc.", "AAPL", "Nasdaq"]]))
        self.assertEqual(Security.objects.get(ticker="AAPL").name_ko, "애플")
