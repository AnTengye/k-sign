# new-api Auto Checkin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a k-sign compliant script that logs into new-api with a single configured account and performs daily check-in, skipping when Turnstile or 2FA is enabled.

**Architecture:** Implement a new `newapi.py` script that extends `BaseSign`, performs a status probe, then login, then check-in using the new-api REST endpoints. Use a small fake session in unit tests to validate status/login/check-in flow without network calls.

**Tech Stack:** Python 3, `requests` (via `BaseSign`), `unittest`.

---

### Task 1: Create failing tests for status and login handling

**Files:**
- Create: `tests/test_newapi_sign.py`

**Step 1: Write the failing test for Turnstile skip**

```python
import os
import unittest

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

    def get(self, url, **kwargs):
        return self._responses.pop(0)

    def post(self, url, **kwargs):
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

if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_newapi_sign.py -v`
Expected: FAIL (ImportError: `newapi` not found)

**Step 3: Write the failing test for 2FA login requirement**

```python
    def test_login_returns_false_when_require_2fa(self):
        s = NewApiSign()
        s.session = FakeSession([
            FakeResponse(payload={"turnstile_check": False, "checkin_enabled": True}),
            FakeResponse(payload={"success": True, "data": {"require_2fa": True}}),
        ])
        s.pre()
        ok = s.login()
        self.assertFalse(ok)
```

**Step 4: Run tests to verify they fail**

Run: `python -m unittest tests/test_newapi_sign.py -v`
Expected: FAIL (methods/classes not implemented)

**Step 5: Commit tests**

```bash
git add tests/test_newapi_sign.py
git commit -m "test: add new-api sign pre/login tests"
```

---

### Task 2: Implement minimal NewApiSign to pass pre/login tests

**Files:**
- Create: `newapi.py`

**Step 1: Implement minimal class and pre/login logic**

```python
# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('new-api每日签到');
"""
import json

from base import BaseSign

class NewApiSign(BaseSign):
    def __init__(self):
        super(NewApiSign, self).__init__("", app_name="new-api", app_key="NEWAPI")
        self.login_type = "login"
        self.exec_method = ["sign"]
        self.skip_login = False

    def pre(self):
        status = self._get_status()
        if status is None:
            return
        if status.get("turnstile_check"):
            self.pwl("Turnstile 已启用，跳过登录")
            self.skip_login = True
            return
        if not status.get("checkin_enabled", True):
            self.pwl("签到未启用，跳过登录")
            self.skip_login = True

    def _get_status(self):
        try:
            resp = self.session.get(f"{self.base_url}/api/status")
        except Exception as e:
            self.pwl(f"状态请求失败: {e}")
            return None
        if resp.status_code != 200:
            self.pwl(f"状态请求失败: HTTP {resp.status_code}")
            return None
        try:
            return resp.json()
        except Exception:
            self.pwl(f"状态解析失败: {resp.text}")
            return None

    def _login(self):
        if self.skip_login:
            return False
        payload = {"username": self.username, "password": self.password}
        try:
            resp = self.session.post(f"{self.base_url}/api/user/login", json=payload)
        except Exception as e:
            self.pwl(f"登录请求失败: {e}")
            return False
        if resp.status_code != 200:
            self.pwl(f"登录失败: HTTP {resp.status_code}")
            return False
        try:
            data = resp.json()
        except Exception:
            self.pwl(f"登录解析失败: {resp.text}")
            return False
        if not data.get("success", False):
            self.pwl(data.get("message", "登录失败"))
            return False
        if data.get("data", {}).get("require_2fa"):
            self.pwl("已启用 2FA，跳过登录")
            return False
        return True

    def sign(self):
        return True

if __name__ == "__main__":
    s = NewApiSign()
    s.run()
```

**Step 2: Run tests to verify they pass**

Run: `python -m unittest tests/test_newapi_sign.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add newapi.py
git commit -m "feat: add new-api sign script skeleton"
```

---

### Task 3: Add failing tests for check-in status and sign flow

**Files:**
- Modify: `tests/test_newapi_sign.py`

**Step 1: Add test for already checked in**

```python
    def test_sign_returns_true_when_checked_in_today(self):
        s = NewApiSign()
        s.session = FakeSession([
            FakeResponse(payload={"success": True, "data": {"stats": {"checked_in_today": True}}})
        ])
        ok = s.sign()
        self.assertTrue(ok)
```

**Step 2: Add test for successful check-in**

```python
    def test_sign_posts_when_not_checked_in(self):
        s = NewApiSign()
        s.session = FakeSession([
            FakeResponse(payload={"success": True, "data": {"stats": {"checked_in_today": False}}}),
            FakeResponse(payload={"success": True, "message": "签到成功", "data": {"quota_awarded": 100}}),
        ])
        ok = s.sign()
        self.assertTrue(ok)
```

**Step 3: Run tests to verify they fail**

Run: `python -m unittest tests/test_newapi_sign.py -v`
Expected: FAIL (sign not implemented)

**Step 4: Commit tests**

```bash
git add tests/test_newapi_sign.py
git commit -m "test: add new-api sign flow tests"
```

---

### Task 4: Implement check-in flow

**Files:**
- Modify: `newapi.py`

**Step 1: Implement sign logic**

```python
    def sign(self):
        try:
            resp = self.session.get(f"{self.base_url}/api/user/checkin")
        except Exception as e:
            self.pwl(f"签到状态请求失败: {e}")
            return False
        if resp.status_code != 200:
            self.pwl(f"签到状态请求失败: HTTP {resp.status_code}")
            return False
        try:
            data = resp.json()
        except Exception:
            self.pwl(f"签到状态解析失败: {resp.text}")
            return False
        if not data.get("success", False):
            self.pwl(data.get("message", "获取签到状态失败"))
            return False
        stats = data.get("data", {}).get("stats", {})
        if stats.get("checked_in_today"):
            self.pwl("今日已签到")
            return True

        try:
            resp = self.session.post(f"{self.base_url}/api/user/checkin")
        except Exception as e:
            self.pwl(f"签到请求失败: {e}")
            return False
        if resp.status_code != 200:
            self.pwl(f"签到失败: HTTP {resp.status_code}")
            return False
        try:
            data = resp.json()
        except Exception:
            self.pwl(f"签到解析失败: {resp.text}")
            return False
        if not data.get("success", False):
            self.pwl(data.get("message", "签到失败"))
            return False
        self.pwl(data.get("message", "签到成功"))
        return True
```

**Step 2: Run tests to verify they pass**

Run: `python -m unittest tests/test_newapi_sign.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add newapi.py
git commit -m "feat: add new-api check-in flow"
```

---

### Task 5: Manual sanity check (optional)

**Files:**
- None

**Step 1: Run script locally**

Run: `set SIGN_URL_NEWAPI=https://example.com; set SIGN_UP_NEWAPI=user|pass; python newapi.py`
Expected: Logs status/login/check-in flow without exceptions.

**Step 2: Commit if any adjustments needed**

```bash
git add newapi.py
git commit -m "chore: refine new-api sign logging"
```
