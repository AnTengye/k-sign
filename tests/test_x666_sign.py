import os
import unittest
from unittest.mock import Mock, patch

from x666 import X666Sign


class X666SignTest(unittest.TestCase):
    def make_sign(self):
        with patch.dict(os.environ, {"SIGN_COOKIE_X666": "auth_token=test-token"}, clear=False):
            return X666Sign()

    def test_login_uses_auth_cookie(self):
        sign = self.make_sign()
        response = Mock(status_code=200)
        response.json.return_value = {"success": True, "username": "tester"}
        sign.session.request = Mock(return_value=response)

        with patch.dict(os.environ, {"SIGN_COOKIE_X666": "auth_token=test-token"}, clear=False):
            self.assertTrue(sign.login())

        self.assertEqual(sign.session.cookies.get("auth_token"), "test-token")

    def test_sign_skips_when_already_done(self):
        sign = self.make_sign()
        sign._request_json = Mock(return_value={"success": True, "can_spin": False})

        self.assertTrue(sign.sign())
        sign._request_json.assert_called_once_with("get", "/api/checkin/status", "签到状态")

    def test_sign_posts_spin_and_logs_reward(self):
        sign = self.make_sign()
        sign._request_json = Mock(side_effect=[
            {"success": True, "can_spin": True},
            {"success": True, "label": "好运", "quota": 100, "new_balance": 200},
        ])

        self.assertTrue(sign.sign())
        self.assertIn("签到成功：好运", sign.log())
        self.assertIn("获得额度：100", sign.log())


if __name__ == "__main__":
    unittest.main()
