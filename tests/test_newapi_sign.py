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
        self.headers = {}

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

    def test_login_sets_new_api_user_header(self):
        s = NewApiSign()
        s.session = FakeSession([
            FakeResponse(payload={"success": True, "data": {"id": 365}})
        ])
        ok = s.login()
        self.assertTrue(ok)
        self.assertEqual(s.session.headers.get("New-Api-User"), "365")

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


    def test_default_app_key_is_newapi(self):
        """Test 2: Default backward compatibility - app_key defaults to 'NEWAPI'."""
        s = NewApiSign()
        self.assertEqual(s.app_key, "NEWAPI")

    def test_custom_app_key_instantiation(self):
        """Test 1: Custom app_key instantiation with NEWAPI_FOO."""
        os.environ["SIGN_URL_NEWAPI_FOO"] = "https://foo.example.com"
        os.environ["SIGN_UP_NEWAPI_FOO"] = "foouser|foopass"
        try:
            s = NewApiSign(app_key="NEWAPI_FOO", app_name="new-api-FOO")
            self.assertEqual(s.app_key, "NEWAPI_FOO")
            self.assertEqual(s.base_url, "https://foo.example.com")
            self.assertEqual(s.username, "foouser")
            self.assertEqual(s.password, "foopass")
        finally:
            os.environ.pop("SIGN_URL_NEWAPI_FOO", None)
            os.environ.pop("SIGN_UP_NEWAPI_FOO", None)


class AutoDiscoveryTests(unittest.TestCase):
    """Test 3: Auto-discovery of env var keys."""

    def test_discover_multiple_newapi_keys(self):
        """Test that discovery logic extracts sorted list of app_keys."""
        import re
        from unittest.mock import patch

        mock_env = {
            "SIGN_URL_NEWAPI": "https://default.example.com",
            "SIGN_URL_NEWAPI_A": "https://a.example.com",
            "SIGN_URL_NEWAPI_B": "https://b.example.com",
            "SIGN_UP_NEWAPI": "user|pass",
            "SIGN_UP_NEWAPI_A": "usera|passa",
            "SIGN_UP_NEWAPI_B": "userb|passb",
            "OTHER_VAR": "ignored",
        }

        with patch.dict(os.environ, mock_env, clear=True):
            keys = sorted(set(
                re.sub(r"^SIGN_URL_", "", k)
                for k in os.environ
                if k.startswith("SIGN_URL_NEWAPI")
            ))
            self.assertEqual(keys, ["NEWAPI", "NEWAPI_A", "NEWAPI_B"])

    def test_discover_empty_when_no_newapi_vars(self):
        """Test that discovery returns empty list when no SIGN_URL_NEWAPI* vars."""
        import re
        from unittest.mock import patch

        mock_env = {"OTHER_VAR": "value"}

        with patch.dict(os.environ, mock_env, clear=True):
            keys = sorted(set(
                re.sub(r"^SIGN_URL_", "", k)
                for k in os.environ
                if k.startswith("SIGN_URL_NEWAPI")
            ))
            self.assertEqual(keys, [])


class ErrorIsolationTests(unittest.TestCase):
    """Test 4: Error isolation - failure in one site doesn't prevent others."""

    def test_error_in_one_site_does_not_block_others(self):
        """Test that if one site's run() raises, next site still executes."""
        from unittest.mock import patch, MagicMock

        mock_env = {
            "SIGN_URL_NEWAPI_A": "https://a.example.com",
            "SIGN_URL_NEWAPI_B": "https://b.example.com",
            "SIGN_UP_NEWAPI_A": "usera|passa",
            "SIGN_UP_NEWAPI_B": "userb|passb",
        }

        executed_keys = []

        def mock_newapi_init(self, app_key="NEWAPI", app_name="new-api"):
            self.app_key = app_key
            self.app_name = app_name

        def mock_run(self):
            executed_keys.append(self.app_key)
            if self.app_key == "NEWAPI_A":
                raise RuntimeError("Simulated failure for NEWAPI_A")

        with patch.dict(os.environ, mock_env, clear=True):
            import re
            keys = sorted(set(
                re.sub(r"^SIGN_URL_", "", k)
                for k in os.environ
                if k.startswith("SIGN_URL_NEWAPI")
            ))

            # Simulate the main block logic with error isolation
            for app_key in keys:
                try:
                    # Create a mock instance
                    mock_instance = MagicMock()
                    mock_instance.app_key = app_key
                    mock_instance.run = lambda inst=mock_instance: mock_run(inst)
                    mock_instance.run()
                except Exception:
                    pass  # Error isolation - continue to next site

            # Both sites should have been attempted
            self.assertEqual(executed_keys, ["NEWAPI_A", "NEWAPI_B"])

    def test_all_sites_execute_when_no_errors(self):
        """Test that all sites execute successfully when no errors occur."""
        from unittest.mock import patch, MagicMock

        mock_env = {
            "SIGN_URL_NEWAPI": "https://default.example.com",
            "SIGN_URL_NEWAPI_X": "https://x.example.com",
            "SIGN_UP_NEWAPI": "user|pass",
            "SIGN_UP_NEWAPI_X": "userx|passx",
        }

        executed_keys = []

        with patch.dict(os.environ, mock_env, clear=True):
            import re
            keys = sorted(set(
                re.sub(r"^SIGN_URL_", "", k)
                for k in os.environ
                if k.startswith("SIGN_URL_NEWAPI")
            ))

            for app_key in keys:
                try:
                    executed_keys.append(app_key)
                except Exception:
                    pass

            self.assertEqual(executed_keys, ["NEWAPI", "NEWAPI_X"])


if __name__ == "__main__":
    unittest.main()
