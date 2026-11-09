import os
import tempfile
import unittest
from unittest.mock import patch

try:
    import base
    import daily_summary
    from newapi import NewApiSign
except ModuleNotFoundError:
    from tests.test_newapi_sign import _install_stubs

    _install_stubs()
    import base
    import daily_summary
    from newapi import NewApiSign


class DailySummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patcher = patch.dict(
            os.environ,
            {
                "SIGN_SUMMARY_DIR": self.temp_dir.name,
                "SIGN_URL_NEWAPI": "https://example.com",
                "SIGN_UP_NEWAPI": "tester|secret",
            },
            clear=False,
        )
        self.env_patcher.start()
        os.environ.pop("SIGN_NOTIFY_EACH", None)

    def tearDown(self):
        self.env_patcher.stop()
        self.temp_dir.cleanup()

    def test_run_records_result_without_individual_notify_by_default(self):
        sent = []
        with patch.object(base, "send", side_effect=lambda title, content: sent.append((title, content))):
            signer = NewApiSign(app_name="测试站点A")
            signer.pre = lambda: None
            signer.login = lambda: True
            signer.sign = lambda: True
            self.assertTrue(signer.run())

        self.assertEqual(sent, [])
        summary = daily_summary.build_daily_summary()
        self.assertEqual(summary, "【今日成功1条，失败0条，失败任务：无】")

    def test_run_sends_individual_notify_when_env_enabled(self):
        sent = []
        os.environ["SIGN_NOTIFY_EACH"] = "1"
        with patch.object(base, "send", side_effect=lambda title, content: sent.append((title, content))):
            signer = NewApiSign(app_name="测试站点A")
            signer.pre = lambda: None
            signer.login = lambda: True
            signer.sign = lambda: True
            self.assertTrue(signer.run())

        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0], "测试站点A")

    def test_build_daily_summary_counts_success_and_failures_and_overwrites_rerun(self):
        base.record_daily_result("akile签到", True, today="2026-11-09")
        base.record_daily_result("2djgame签到", False, today="2026-11-09")
        base.record_daily_result("飞雪acg签到", False, today="2026-11-09")

        self.assertEqual(
            daily_summary.build_daily_summary(today="2026-11-09"),
            "【今日成功1条，失败2条，失败任务：2djgame签到、飞雪acg签到】",
        )

        # Rerunning a failed task updates the same day's status to success
        base.record_daily_result("2djgame签到", True, today="2026-11-09")
        self.assertEqual(
            daily_summary.build_daily_summary(today="2026-11-09"),
            "【今日成功2条，失败1条，失败任务：飞雪acg签到】",
        )

    def test_main_sends_summary_notification(self):
        base.record_daily_result("hostloc签到", True)
        base.record_daily_result("南+登录", False)
        sent = []
        with patch.object(daily_summary, "send", side_effect=lambda title, content: sent.append((title, content))):
            text = daily_summary.main()

        self.assertEqual(text, "【今日成功1条，失败1条，失败任务：南+登录】")
        self.assertEqual(sent, [("每日签到汇总", "【今日成功1条，失败1条，失败任务：南+登录】")])


if __name__ == "__main__":
    unittest.main()
