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

    def get(self, url, **kwargs):
        if urlsplit(url).path == DuPanSign.CLAIM:
            self.calls.append((DuPanSign.CLAIM, kwargs))
            if self.claim_apply:
                self.task_status = 1
                self.points += 6
                self.growth += 3
            return Response({"errno": self.claim_code,
                             "result": {"addScore": 6, "addGrowScore": 3}})
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
