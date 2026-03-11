import os
import sys
import types
import unittest


def _install_stubs():
    if "requests" in sys.modules:
        return

    class DummyRetry:
        def __init__(self, *args, **kwargs):
            pass

    class DummyHTTPAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def send(self, request, **kwargs):
            return None

    class DummySession:
        def __init__(self):
            self.headers = {}
            self.proxies = {}
            self.verify = True

        def mount(self, *args, **kwargs):
            return None

        def get(self, url, **kwargs):
            raise NotImplementedError

        def post(self, url, **kwargs):
            raise NotImplementedError

    def disable_warnings(*args, **kwargs):
        return None

    def create_urllib3_context(*args, **kwargs):
        return None

    requests_module = types.ModuleType("requests")
    requests_module.session = lambda: DummySession()
    requests_module.Session = DummySession
    requests_module.packages = types.SimpleNamespace(
        urllib3=types.SimpleNamespace(disable_warnings=disable_warnings)
    )

    requests_adapters_module = types.ModuleType("requests.adapters")
    requests_adapters_module.HTTPAdapter = DummyHTTPAdapter

    urllib3_util_retry_module = types.ModuleType("requests.packages.urllib3.util.retry")
    urllib3_util_retry_module.Retry = DummyRetry

    urllib3_util_ssl_module = types.ModuleType("requests.packages.urllib3.util.ssl_")
    urllib3_util_ssl_module.create_urllib3_context = create_urllib3_context

    sys.modules["requests"] = requests_module
    sys.modules["requests.adapters"] = requests_adapters_module
    sys.modules["requests.packages"] = types.ModuleType("requests.packages")
    sys.modules["requests.packages.urllib3"] = types.ModuleType("requests.packages.urllib3")
    sys.modules["requests.packages.urllib3.util"] = types.ModuleType("requests.packages.urllib3.util")
    sys.modules["requests.packages.urllib3.util.retry"] = urllib3_util_retry_module
    sys.modules["requests.packages.urllib3.util.ssl_"] = urllib3_util_ssl_module

    scrapy_module = types.ModuleType("scrapy")
    class DummySelector:
        def __init__(self, *args, **kwargs):
            pass

    scrapy_module.Selector = DummySelector
    sys.modules["scrapy"] = scrapy_module

    gifcode_module = types.ModuleType("gifcode")
    gifcode_module.handle_yzm = lambda *args, **kwargs: ""
    sys.modules["gifcode"] = gifcode_module

    notify_module = types.ModuleType("notify")
    notify_module.send = lambda *args, **kwargs: None
    sys.modules["notify"] = notify_module


_install_stubs()

from newapi import NewApiSign


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("invalid json")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url))
        return self._responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("post", url))
        return self._responses.pop(0)


class NewApiSignTests(unittest.TestCase):
    def setUp(self):
        os.environ["SIGN_URL_NEWAPI"] = "https://example.com"
        os.environ["SIGN_UP_NEWAPI"] = "user|pass"

    def test_pre_sets_skip_when_turnstile_enabled(self):
        s = NewApiSign()
        s.session = FakeSession([
            FakeResponse(payload={"turnstile_check": True, "checkin_enabled": True})
        ])
        s.pre()
        self.assertTrue(s.skip_login)

    def test_login_returns_false_when_require_2fa(self):
        s = NewApiSign()
        s.session = FakeSession([
            FakeResponse(payload={"turnstile_check": False, "checkin_enabled": True}),
            FakeResponse(payload={"success": True, "data": {"require_2fa": True}}),
        ])
        s.pre()
        ok = s.login()
        self.assertFalse(ok)

    def test_sign_returns_true_when_checked_in_today(self):
        s = NewApiSign()
        s.session = FakeSession([
            FakeResponse(payload={"success": True, "data": {"stats": {"checked_in_today": True}}})
        ])
        ok = s.sign()
        self.assertTrue(ok)
        self.assertEqual(
            s.session.calls,
            [("get", "https://example.com/api/user/checkin")],
        )

    def test_sign_posts_when_not_checked_in(self):
        s = NewApiSign()
        s.session = FakeSession([
            FakeResponse(payload={"success": True, "data": {"stats": {"checked_in_today": False}}}),
            FakeResponse(payload={"success": True, "message": "签到成功", "data": {"quota_awarded": 100}}),
        ])
        ok = s.sign()
        self.assertTrue(ok)
        self.assertEqual(
            s.session.calls,
            [
                ("get", "https://example.com/api/user/checkin"),
                ("post", "https://example.com/api/user/checkin"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
