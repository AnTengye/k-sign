import copy
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

# Match the repository's dependency-free test runner; all business HTTP is synthetic.
from tests.test_newapi_sign import _install_stubs
_install_stubs()

from dupan import (DuPanError, DuPanSign, ORIGIN, STATIC_KEYS, directory_lock,
                   import_profile, main, read_json, validate_profile, write_json)


PROFILE = {"origin": ORIGIN, "cookie": "BDUSS=synthetic-secret; STOKEN=synthetic-token; BAIDUID=synthetic-id",
           "native_static_params": {key: "synthetic-" + key for key in STATIC_KEYS},
           "user_agent": "Synthetic UA"}
TASK_ID = "98765432101234567890"


class Response:
    def __init__(self, payload, code=200):
        self.payload, self.status_code = payload, code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield json.dumps(self.payload).encode()


class Service:
    def __init__(self, signed=0):
        self.signed = signed
        self.days, self.points, self.growth = 4, 46, 86848
        self.calls = []
        self.failure = None
        self.apply = True
        self.login_code = 0
        self.list_signed = None
        self.server_age = 0
        self.tasks = [{"task_type": "166", "task_id_str": TASK_ID, "task_from": "task_sys_daily"}]

    def get(self, url, **kwargs):
        path = urlsplit(url).path
        self.calls.append((path, kwargs))
        if path == DuPanSign.LOGIN:
            return Response({"errno": self.login_code, "login_info": {"uk_str": "12345"}})
        if path == DuPanSign.HOME:
            return Response({"errno": 0, "data": {"signed": self.signed, "signin_days": self.days,
                                                  "points_balance": self.points}})
        if path == DuPanSign.TASKS:
            return Response({"errno": 0, "result": {"list": self.tasks}})
        if path == DuPanSign.SIGN_LIST:
            return Response({"errno": 0, "data": {"signed_today": self.signed if self.list_signed is None else self.list_signed,
                           "signin_days": self.days, "date": int(time.time()) - self.server_age}})
        if path == DuPanSign.USER:
            return Response({"error_code": 0, "level_info": {"current_value": self.growth}})
        if path == DuPanSign.SIGN:
            if self.apply:
                self.signed = 1
                self.days += 1
                self.points += 6
                self.growth += 14
            if isinstance(self.failure, Exception):
                raise self.failure
            if self.failure == "http":
                return Response({}, 503)
            return Response({"errno": 8001 if self.failure else 0, "errmsg": "synthetic-secret"})
        raise AssertionError("Unexpected endpoint")

    def mutations(self):
        return [call for call in self.calls if call[0] == DuPanSign.SIGN]


class DuPanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "dupan"
        self.source = Path(self.temp.name) / "source.json"
        write_json(self.source, PROFILE)
        self.env = patch.dict(os.environ, {"SIGN_AUTH_DUPAN": str(self.source),
                                          "SIGN_STATE_DIR_DUPAN": str(self.directory)}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.output = io.StringIO()
        self.console = patch("sys.stdout", self.output)
        self.console.start()
        self.addCleanup(self.console.stop)

    def signer(self, service, read_only=False):
        sign = DuPanSign(read_only=read_only)
        sign.session.get = service.get
        return sign

    def run_sign(self, service, read_only=False):
        sign = self.signer(service, read_only)
        sign._exec("")
        return sign

    def test_fresh_sign_uses_exact_s1_and_reads_both_states_and_balances(self):
        service = Service()
        sign = self.run_sign(service)
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.report["delta"], {"points": 6, "growth": 14, "signin_days": 1})
        self.assertEqual(len(service.mutations()), 1)
        self.assertEqual([p for p, _ in service.calls],
                         [sign.LOGIN, sign.HOME, sign.TASKS, sign.SIGN_LIST, sign.USER,
                          sign.SIGN, sign.HOME, sign.SIGN_LIST, sign.USER])
        params = service.mutations()[0][1]["params"]
        self.assertEqual(set(params), STATIC_KEYS | sign.BUSINESS_KEYS | {"rand", "time"})
        self.assertEqual(params["task_id"], TASK_ID)
        self.assertEqual(params["task_id_str"], TASK_ID)
        self.assertEqual(params["task_from"], "task_sys_daily")
        self.assertEqual(params["is_growth"], "1")
        self.assertEqual(len({kw["params"]["rand"] for _, kw in service.calls}), len(service.calls))
        self.assertTrue(all(kw["allow_redirects"] is False and kw["timeout"] == 25 for _, kw in service.calls))
        self.assertEqual(read_json(sign.ledger_path)["status"], "signed")

    def test_already_signed_stops_before_tasks_and_mutations(self):
        service = Service(signed=1)
        sign = self.run_sign(service)
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.report["status"], "already_signed")
        self.assertEqual([p for p, _ in service.calls], [sign.LOGIN, sign.HOME])
        self.assertEqual(sign.mutation_count, 0)

    def test_read_only_unsigned_sends_no_mutation(self):
        service = Service()
        sign = self.run_sign(service, read_only=True)
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.report["status"], "unsigned_read_only")
        self.assertFalse(service.mutations())

    def test_invalid_login_and_ambiguous_home_stop_before_mutation(self):
        for mode in ("login", "home"):
            with self.subTest(mode=mode):
                service = Service()
                if mode == "login":
                    service.login_code = -6
                else:
                    service.signed = 2
                sign = self.run_sign(service)
                self.assertFalse(sign.last_run_success)
                self.assertFalse(service.mutations())

    def test_task_id_missing_or_ambiguous_never_submits(self):
        for tasks in ([], [{"task_type": 166, "task_id": 98765432101234567890, "task_from": "task_sys_daily"}],
                      [{"task_type": 166, "task_id_str": TASK_ID, "task_from": "other"}]):
            with self.subTest(tasks=tasks):
                service = Service()
                service.tasks = tasks
                self.assertFalse(self.run_sign(service).last_run_success)
                self.assertFalse(service.mutations())

    def test_stale_date_or_disagreeing_signinlist_blocks_mutation(self):
        for mode in ("date", "status"):
            with self.subTest(mode=mode):
                service = Service()
                if mode == "date":
                    service.server_age = 86400
                else:
                    service.list_signed = 1
                self.assertFalse(self.run_sign(service).last_run_success)
                self.assertFalse(service.mutations())

    def test_timeout_business_error_and_http_error_read_back_without_retries(self):
        for index, failure in enumerate((TimeoutError("synthetic-secret"), "business", "http")):
            with self.subTest(failure=type(failure).__name__):
                os.environ["SIGN_STATE_DIR_DUPAN"] = str(self.directory / str(index))
                service = Service()
                service.apply, service.failure = False, failure
                sign = self.run_sign(service)
                self.assertFalse(sign.last_run_success)
                self.assertEqual(len(service.mutations()), 1)
                self.assertEqual(sign.report["after"]["signed"], 0)
                self.assertEqual(sign.report["delta"]["points"], 0)
                self.assertNotIn("synthetic-secret", json.dumps(sign.report))
                # A new process with the same server-side account still cannot resubmit today.
                again = self.run_sign(service)
                self.assertFalse(again.last_run_success)
                self.assertEqual(again.mutation_count, 0)
                self.assertEqual(len(service.mutations()), 1)

    def test_timeout_that_committed_is_recorded_but_not_misreported_as_clean_success(self):
        service = Service()
        service.failure = TimeoutError("secret")
        sign = self.run_sign(service)
        self.assertFalse(sign.last_run_success)
        self.assertEqual(sign.report["after"]["signed"], 1)
        self.assertEqual(sign.report["delta"]["growth"], 14)
        self.assertEqual(len(service.mutations()), 1)

    def test_success_code_without_state_change_is_not_success(self):
        service = Service()
        service.apply = False
        sign = self.run_sign(service)
        self.assertFalse(sign.last_run_success)
        self.assertEqual(len(service.mutations()), 1)

    def test_ledger_is_saved_before_send_and_lock_is_held(self):
        service = Service()
        original = service.get
        sign = self.signer(service)
        def get(url, **kwargs):
            if urlsplit(url).path == sign.SIGN:
                self.assertEqual(read_json(sign.ledger_path)["status"], "attempting")
                with self.assertRaises(DuPanError), directory_lock(self.directory):
                    pass
            return original(url, **kwargs)
        sign.session.get = get
        sign._exec("")
        self.assertTrue(sign.last_run_success)

    def test_concurrent_run_stops_without_any_http(self):
        service = Service()
        with directory_lock(self.directory):
            sign = self.run_sign(service)
        self.assertFalse(sign.last_run_success)
        self.assertFalse(service.calls)

    def test_cookie_refresh_survives_reload_and_explicit_source_update_reimports(self):
        first = self.run_sign(Service(signed=1))
        for cookie in first.session.cookies:
            if cookie.name == "STOKEN":
                cookie.value = "refreshed-secret"
                cookie.expires = int(time.time()) + 7200
        first._persist()
        second = self.run_sign(Service(signed=1))
        refreshed = next(c for c in second.session.cookies if c.name == "STOKEN")
        self.assertEqual(refreshed.value, "refreshed-secret")
        self.assertIsNotNone(refreshed.expires)
        os.environ["SIGN_COOKIE_DUPAN"] = "BDUSS=updated-secret; STOKEN=updated-token"
        third = self.run_sign(Service(signed=1))
        self.assertEqual(next(c.value for c in third.session.cookies if c.name == "STOKEN"), "updated-token")
        self.assertNotEqual(first.source_digest, third.source_digest)

    def test_environment_only_profile_compatible_and_preserves_url_configuration(self):
        os.environ.pop("SIGN_AUTH_DUPAN")
        os.environ.update(SIGN_COOKIE_DUPAN=PROFILE["cookie"],
                          SIGN_CLIENT_DUPAN=json.dumps(PROFILE["native_static_params"]),
                          SIGN_USER_AGENT_DUPAN=PROFILE["user_agent"],
                          SIGN_URL_DUPAN="https://untrusted.invalid")
        sign = self.run_sign(Service(signed=1))
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.base_url, ORIGIN)
        self.assertEqual(os.environ["SIGN_URL_DUPAN"], "https://untrusted.invalid")
        self.assertFalse(sign.session.trust_env)

    def test_old_cookie_only_configuration_fails_before_network(self):
        os.environ.pop("SIGN_AUTH_DUPAN")
        os.environ["SIGN_COOKIE_DUPAN"] = PROFILE["cookie"]
        service = Service()
        self.assertFalse(self.run_sign(service).last_run_success)
        self.assertFalse(service.calls)

    def test_import_has_private_permissions_and_never_overwrites(self):
        imported = import_profile(self.source, self.directory)
        self.assertEqual(read_json(imported), validate_profile(PROFILE))
        self.assertEqual(imported.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        with self.assertRaises(DuPanError):
            import_profile(self.source, self.directory)

    def test_report_and_logs_contain_no_credential_or_device_values(self):
        sign = self.run_sign(Service())
        contents = self.output.getvalue() + json.dumps(sign.report)
        for value in ("synthetic-secret", "synthetic-token", "synthetic-cuid", PROFILE["user_agent"]):
            self.assertNotIn(value, contents)
        self.assertEqual((self.directory / "session.json").stat().st_mode & 0o777, 0o600)
        reports = list((self.directory / "reports").glob("*.json"))
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].stat().st_mode & 0o777, 0o600)

    def test_static_dynamic_injection_is_rejected(self):
        for key in ("z", "rand2", "jt", "hjs", "token"):
            profile = copy.deepcopy(PROFILE)
            profile["native_static_params"][key] = "old"
            with self.assertRaises(DuPanError):
                validate_profile(profile)

    def test_adapter_retries_are_explicitly_disabled(self):
        with patch("dupan.HTTPAdapter") as adapter:
            self.signer(Service())
        self.assertEqual(adapter.call_count, 2)
        adapter.assert_called_with(max_retries=0)

    def test_unlisted_endpoints_and_second_in_process_sign_are_blocked(self):
        sign = self.run_sign(Service())
        for path, params in (("/rest/2.0/membership/level", {"method": "signin"}),
                             (sign.SIGN, {k: "1" for k in sign.BUSINESS_KEYS}),
                             (sign.HOME, {"z": "injected"})):
            with self.assertRaises(DuPanError):
                sign._request_json(path, params)

    def test_status_cli_never_sends_notifications(self):
        sign = self.signer(Service(signed=1), read_only=True)
        sign.run = Mock(side_effect=AssertionError("must not notify"))
        with patch("dupan.DuPanSign", return_value=sign):
            self.assertEqual(main(["--status"]), 0)
        sign.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
