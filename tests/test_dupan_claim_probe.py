import hashlib
import json
import subprocess
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import tests.test_dupan_sign as sign_tests
from tests.test_dupan_answer import QuestionService
from tests.test_dupan_sign import PROFILE, Response
from dupan import DuPanError, DuPanSign, STATIC_KEYS, TASK_TOKEN_SALT, create_htj_token, read_json, write_json
from dupan_signing import native_rand_pair, native_rchannel


UID = "123456789"
ENCRYPTED_SK = "R7A0VSkyHLCChONU5mM2QnOAu6R7m3s+RL/Pz3mKABc="


class ClaimService(QuestionService):
    def __init__(self):
        super().__init__(answer_status=1, task_status=6)
        self.claim_apply = True
        self.claim_code = 0
        self.claim_result = {"addScore": 6, "addGrowScore": 3}

    def get(self, url, **kwargs):
        if urlsplit(url).path == DuPanSign.CLAIM:
            self.calls.append((DuPanSign.CLAIM, kwargs))
            if self.claim_apply:
                self.task_status = 1
                self.points += 6
                self.growth += 3
            return Response({"errno": self.claim_code, "result": self.claim_result})
        return super().get(url, **kwargs)

    def claims(self):
        return [kwargs for path, kwargs in self.calls if path == DuPanSign.CLAIM]


class ClaimProbeTests(unittest.TestCase):
    setUp = sign_tests.DuPanTests.setUp

    def configure(self):
        profile = json.loads(json.dumps(PROFILE))
        profile["native_static_params"]["version"] = "13.32.1"
        write_json(self.source, profile)
        self.directory.mkdir(mode=0o700, exist_ok=True)
        write_json(self.directory / "claim-signing.json", {
            "uid": UID, "encrypted_sk": ENCRYPTED_SK,
            "account_uk_sha256": hashlib.sha256(b"12345").hexdigest()})
        write_json(self.directory / "sofire-material.json", {
            "seed": "0123456789ABCDEF0123456789ABCDEF", "status": 0,
            "flag1": 1, "flag2": 2, "flag3": "03",
            "version": profile["native_static_params"]["version"],
            "offlinepackage": {"feature": {"version": "1"}}, "themeinfo": 0,
            "account_uk_sha256": hashlib.sha256(b"12345").hexdigest(),
            "cuid_sha256": hashlib.sha256(profile["native_static_params"]["cuid"].encode()).hexdigest()})

    def run_probe(self, service):
        sign = DuPanSign(claim_probe=True)
        sign.session.get = service.get
        with patch("dupan.create_htj_token", return_value={"jt": "synthetic-jt", "version": "3.5.11"}):
            sign._exec("")
        return sign

    def run_daily(self, service):
        sign = DuPanSign(include_answer=True)
        sign.session.get = service.get
        with patch("dupan.create_htj_token", return_value={"jt": "synthetic-jt", "version": "3.5.11"}):
            sign._exec("")
        return sign

    def test_one_probe_claims_and_verifies_balances(self):
        self.configure()
        service = ClaimService()
        sign = self.run_probe(service)
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.report["answer"]["status"], "claimed")
        self.assertEqual(sign.report["answer"]["balance_delta"], {"points": 6, "growth": 3})
        self.assertEqual(len(service.claims()), 1)
        params = service.claims()[0]["params"]
        self.assertEqual(set(params), STATIC_KEYS | {"task_ids", "task_froms", "uk", "action",
                                                     "rand", "rand2", "time", "token", "z",
                                                     "jt", "aid", "ev", "hjs", "c", "ver", "ua",
                                                     "offlinepackage", "themeinfo"})
        self.assertEqual(params["action"], "receive_award")
        self.assertEqual(params["jt"], "synthetic-jt")
        self.assertEqual(params["aid"], "13655")
        self.assertEqual(params["ev"], "task")
        self.assertEqual(len(params["z"]), 60)
        self.assertEqual(params["offlinepackage"], '{"feature":{"version":"1"}}')
        self.assertEqual((params["rand"], params["rand2"]), native_rand_pair(
            PROFILE["cookie"].split(";", 1)[0].split("=", 1)[1], UID, ENCRYPTED_SK,
            params["time"], params["devuid"], params["version"]))
        self.assertEqual(params["rchannel"], native_rchannel(UID, params["time"], params["channel"]))
        payload = "_".join((params["task_ids"], params["uk"], params["rand"],
                            params["time"], TASK_TOKEN_SALT))
        self.assertEqual(params["token"], hashlib.md5(payload.encode()).hexdigest())
        self.assertIn("claim_probe", read_json(sign.question_ledger_path))
        self.assertNotIn(ENCRYPTED_SK, json.dumps(sign.report))
        self.assertNotIn("synthetic-jt", json.dumps(sign.report))
        again = self.run_probe(service)
        self.assertFalse(again.last_run_success)
        self.assertEqual(again.report["answer"]["status"], "already_claimed_no_probe")
        self.assertEqual(again.mutation_count, 0)

    def test_rejection_or_uncertain_state_never_retries(self):
        self.configure()
        service = ClaimService()
        service.claim_apply = False
        service.claim_code = 8001
        first = self.run_probe(service)
        self.assertFalse(first.last_run_success)
        self.assertEqual(first.report["answer"]["status"], "claim_needs_review")
        second = self.run_probe(service)
        self.assertFalse(second.last_run_success)
        self.assertEqual(len(service.claims()), 1)

    def test_daily_answers_reports_claims_and_does_not_repeat(self):
        self.configure()
        service = ClaimService()
        service.answer_status = -1
        service.task_status = 0
        first = self.run_daily(service)
        self.assertTrue(first.last_run_success)
        self.assertEqual(first.report["answer"]["status"], "claimed")
        self.assertEqual(first.report["answer"]["task_status"], 1)
        self.assertEqual(first.report["answer"]["balance_delta"], {"points": 6, "growth": 3})
        self.assertEqual(first.report["answer"]["reward_response"], {"points": 6, "growth": 3})
        self.assertEqual([path for path, _ in service.calls if path in first.MUTATIONS],
                         [first.ANSWER, first.REPORT, first.CLAIM])
        self.assertEqual(first.mutation_count, 3)
        self.assertIn("claim", read_json(first.question_ledger_path))
        self.assertNotIn("synthetic-jt", json.dumps(first.report))
        again = self.run_daily(service)
        self.assertTrue(again.last_run_success)
        self.assertEqual(again.report["answer"]["status"], "already_claimed")
        self.assertEqual(again.mutation_count, 0)
        self.assertEqual(len(service.claims()), 1)

    def test_daily_accepts_server_readback_without_numeric_reward_response(self):
        self.configure()
        service = ClaimService()
        service.claim_result = None
        sign = self.run_daily(service)
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.report["answer"]["status"], "claimed_readback_only")
        self.assertEqual(sign.report["answer"]["reward_response_shape"]["result_type"], "NoneType")
        self.assertNotIn("reward_response", sign.report["answer"])
        self.assertEqual(sign.report["answer"]["balance_delta"], {"points": 6, "growth": 3})

    def test_daily_parses_single_item_reward_response(self):
        self.configure()
        service = ClaimService()
        service.claim_result = [{"addScore": 6, "addGrowScore": 3}]
        sign = self.run_daily(service)
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.report["answer"]["status"], "claimed")
        self.assertEqual(sign.report["answer"]["reward_response"], {"points": 6, "growth": 3})
        self.assertEqual(sign.report["answer"]["reward_response_shape"]["result_type"], "list")

    def test_status_with_claim_material_never_claims(self):
        self.configure()
        service = ClaimService()
        sign = DuPanSign(read_only=True, include_answer=True)
        sign.session.get = service.get
        sign._exec("")
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.report["answer"]["status"], "read_only")
        self.assertFalse(service.claims())

    def test_daily_rejection_and_manual_probe_share_once_only_ledger(self):
        self.configure()
        service = ClaimService()
        service.claim_apply = False
        service.claim_code = 8001
        first = self.run_daily(service)
        self.assertFalse(first.last_run_success)
        self.assertEqual(first.report["answer"]["status"], "claim_needs_review")
        second = self.run_daily(service)
        self.assertFalse(second.last_run_success)
        self.assertEqual(second.report["answer"]["status"], "claim_skipped_prior_attempt")
        self.assertFalse(self.run_probe(service).last_run_success)
        self.assertEqual(len(service.claims()), 1)

    def test_daily_never_retries_after_manual_probe_or_mismatched_reward(self):
        self.configure()
        service = ClaimService()
        service.claim_apply = False
        service.claim_code = 8001
        self.assertFalse(self.run_probe(service).last_run_success)
        self.assertFalse(self.run_daily(service).last_run_success)
        self.assertEqual(len(service.claims()), 1)

        service = ClaimService()
        service.claim_result = {"addScore": 7, "addGrowScore": 3}
        # A new isolated account/day ledger for the response mismatch case.
        self.directory = self.source.parent / "mismatch-state"
        with patch.dict("os.environ", {"SIGN_STATE_DIR_DUPAN": str(self.directory)}):
            self.configure()
            first = self.run_daily(service)
            self.assertFalse(first.last_run_success)
            self.assertEqual(first.report["answer"]["status"], "claim_needs_review")
            self.assertFalse(self.run_probe(service).last_run_success)
        self.assertEqual(len(service.claims()), 1)

    def test_previous_day_probe_does_not_block_new_day_claim(self):
        self.configure()
        service = ClaimService()
        initial = DuPanSign(read_only=True, include_answer=True)
        initial.session.get = service.get
        self.assertTrue(initial.login())
        write_json(initial.question_ledger_path, {
            "day": "2000-01-01", "ask_id": "1", "task_id_str": "2",
            "claim_probe": {"status": "attempting"}})
        sign = self.run_daily(service)
        self.assertTrue(sign.last_run_success)
        self.assertEqual(sign.report["answer"]["status"], "claimed")
        self.assertEqual(len(service.claims()), 1)

    def test_missing_security_or_non_waiting_task_never_claims(self):
        service = ClaimService()
        self.assertFalse(self.run_probe(service).last_run_success)
        self.assertFalse(service.claims())
        self.configure()
        service.task_status = 0
        self.assertFalse(self.run_probe(service).last_run_success)
        self.assertFalse(service.claims())

    def test_missing_sofire_material_never_claims(self):
        self.configure()
        (self.directory / "sofire-material.json").unlink()
        service = ClaimService()
        self.assertFalse(self.run_probe(service).last_run_success)
        self.assertFalse(service.claims())

    def test_htj_runner_accepts_only_valid_machine_output(self):
        good = subprocess.CompletedProcess([], 0, '{"jt":"synthetic-jt","version":"3.5.11"}', "")
        with patch("dupan.subprocess.run", return_value=good) as runner:
            self.assertEqual(create_htj_token("cuid", "ua")["jt"], "synthetic-jt")
            sent = json.loads(runner.call_args.kwargs["input"])
            self.assertEqual(set(sent), {"cuid", "userAgent", "proxy"})
            self.assertNotIn("cookie", sent)
        bad = subprocess.CompletedProcess([], 0, '{"jt":"","version":"3.5.11"}', "")
        with patch("dupan.subprocess.run", return_value=bad):
            with self.assertRaises(DuPanError):
                create_htj_token("cuid", "ua")


if __name__ == "__main__":
    unittest.main()
