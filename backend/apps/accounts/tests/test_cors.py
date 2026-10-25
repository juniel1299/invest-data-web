from django.test import TestCase, override_settings


@override_settings(DEBUG=False)
class CorsTests(TestCase):
    def test_flutter_dev_origin_allowed(self):
        res = self.client.options(
            "/api/auth/register/",
            HTTP_ORIGIN="http://localhost:54321",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:54321")

    def test_other_origin_blocked(self):
        res = self.client.options(
            "/api/auth/register/",
            HTTP_ORIGIN="http://evil.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertNotIn("access-control-allow-origin", res.headers)
