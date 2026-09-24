import hashlib
import json
import time
import unittest
from urllib.parse import urlsplit

import tests.test_dupan_sign as sign_tests
from tests.test_dupan_sign import Response, Service
from dupan import DuPanSign, STATIC_KEYS, TASK_TOKEN_SALT, read_json


QUESTION_ID = "8123456789012345678"
GROWTH_TASK_ID = "7123456789012345678"


class QuestionService(Service):
    def __init__(self, answer_status=-1, task_status=0):
        super().__init__(signed=1)
        self.answer_status = answer_status
        self.task_status = task_status
        self.question_time = int(time.time())
        self.answer_apply = True
        self.report_apply = True
        self.answer_failure = None
        self.report_failure = None

    def get(self, url, **kwargs):
        path = urlsplit(url).path
        if path == DuPanSign.QUESTION:
            self.calls.append((path, kwargs))
            return Response({"errno": 0, "data": {"ask_id": int(QUESTION_ID), "ask_time": self.question_time,
                                                  "answer": 1, "answer_status": self.answer_status, "score": 3}})
        if path == DuPanSign.GROWTH_TASKS:
            self.calls.append((path, kwargs))
            return Response({"errno": 0, "result": {"list": [{"task_type": 169,
                    "task_id_str": GROWTH_TASK_ID, "task_from": "task_sys_task_growth",
                    "task_status": self.task_status}]}})
        if path == DuPanSign.ANSWER:
            self.calls.append((path, kwargs))
            if self.answer_apply:
                self.answer_status = 1
            if self.answer_failure:
                raise self.answer_failure
            return Response({"errno": 0, "data": {"answer_status": self.answer_status}})
        if path == DuPanSign.REPORT:
            self.calls.append((path, kwargs))
            if self.report_apply:
                self.task_status = 6
            if self.report_failure:
                raise self.report_failure
            return Response({"errno": 0})
        return super().get(url, **kwargs)

    def question_mutations(self):
        return [(path, kwargs) for path, kwargs in self.calls
                if path in {DuPanSign.ANSWER, DuPanSign.REPORT}]


class DuPanAnswerTests(unittest.TestCase):
    setUp = sign_tests.DuPanTests.setUp

    def run_answer(self, service, read_only=False):
        sign = DuPanSign(read_only=read_only, include_answer=True)
        sign.session.get = service.get
        sign._exec("")
        return sign

    def test_fresh_question_answers_and_reports_once_with_local_token(self):
        service = QuestionService()
        sign = self.run_answer(service)
        self.assertTrue(sign.sign_success)
        self.assertFalse(sign.last_run_success)
        self.assertEqual(sign.report["answer"]["status"], "waiting_reward")
        self.assertEqual([path for path, _ in service.question_mutations()], [sign.ANSWER, sign.REPORT])
        self.assertEqual(sign.mutation_count, 2)
        answer_params = service.question_mutations()[0][1]["params"]
        self.assertEqual(set(answer_params), STATIC_KEYS | {"ask_id", "answer", "rand", "time"})
        self.assertEqual(answer_params["ask_id"], QUESTION_ID)
        report_params = service.question_mutations()[1][1]["params"]
        self.assertEqual(set(report_params), STATIC_KEYS | {"task_id", "task_from", "uk", "rand", "time", "token"})
        self.assertEqual(report_params["task_id"], GROWTH_TASK_ID)
        payload = "_".join((report_params["task_id"], report_params["uk"], report_params["rand"],
                            report_params["time"], TASK_TOKEN_SALT))
        self.assertEqual(report_params["token"], hashlib.md5(payload.encode()).hexdigest())
        self.assertEqual(read_json(sign.question_ledger_path)["report"]["status"], "attempting")
        self.assertNotIn(report_params["token"], json.dumps(sign.report))
        self.assertEqual(self.run_answer(service).mutation_count, 0)

    def test_answer_timeout_and_unchanged_state_never_retry(self):
        service = QuestionService()
        service.answer_apply = False
        service.answer_failure = TimeoutError("synthetic-secret")
        first = self.run_answer(service)
        self.assertEqual(first.report["answer"]["status"], "answer_needs_review")
        second = self.run_answer(service)
        self.assertFalse(second.last_run_success)
        self.assertEqual([path for path, _ in service.question_mutations()], [first.ANSWER])
        self.assertNotIn("synthetic-secret", json.dumps(first.report) + json.dumps(second.report))

    def test_resume_after_answer_reports_without_answering_again(self):
        service = QuestionService(answer_status=1)
        sign = self.run_answer(service)
        self.assertEqual([path for path, _ in service.question_mutations()], [sign.REPORT])
        self.assertEqual(sign.report["answer"]["status"], "waiting_reward")

    def test_report_timeout_does_not_repeat_after_state_change(self):
        service = QuestionService(answer_status=1)
        service.report_failure = TimeoutError("synthetic-secret")
        first = self.run_answer(service)
        self.assertEqual(first.report["answer"]["status"], "report_needs_review")
        second = self.run_answer(service)
        self.assertEqual(second.report["answer"]["status"], "waiting_reward")
        self.assertEqual([path for path, _ in service.question_mutations()], [first.REPORT])

    def test_read_only_and_already_claimed_never_mutate(self):
        service = QuestionService()
        check = self.run_answer(service, read_only=True)
        self.assertTrue(check.last_run_success)
        self.assertEqual(check.report["answer"]["status"], "read_only")
        self.assertFalse(service.question_mutations())
        service.answer_status, service.task_status = 1, 1
        done = self.run_answer(service)
        self.assertTrue(done.last_run_success)
        self.assertEqual(done.report["answer"]["status"], "already_claimed")
        self.assertFalse(service.question_mutations())

    def test_stale_question_day_blocks_mutation(self):
        service = QuestionService()
        service.question_time -= 86400
        self.assertFalse(self.run_answer(service).last_run_success)
        self.assertFalse(service.question_mutations())


if __name__ == "__main__":
    unittest.main()
