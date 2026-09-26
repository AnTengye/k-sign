# -*- coding:utf-8 -*-
"""
cron: 0 20 8 * * *
new Env('百度网盘任务中心签到');

SIGN_AUTH_DUPAN: 私有登录资料 JSON（兼容 one-tap-capture 格式）。
或 SIGN_COOKIE_DUPAN + SIGN_CLIENT_DUPAN（静态字段 JSON）+ SIGN_USER_AGENT_DUPAN。
SIGN_STATE_DIR_DUPAN: 持久目录，青龙默认 /ql/data/dupan，本地默认 data/dupan。
先执行任务中心签到，再完成每日答题、任务上报与纯脚本领奖。
--claim-probe 保留为人工单独核验入口；与每日流程共用当天一次提交防重。
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
from http.cookiejar import Cookie, CookieJar
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time

from requests.adapters import HTTPAdapter

from base import BaseSign
from dupan_signing import native_rand_pair, native_rchannel, sofire_z


ORIGIN = "https://pan.baidu.com"
SHANGHAI = timezone(timedelta(hours=8))
TASK_TOKEN_SALT = "ae82c240578eb391de93c2f4c3dfc3ba"
STATIC_KEYS = {"app", "channel", "clienttype", "cuid", "devuid", "rchannel", "version", "versioncode"}
COOKIE_FIELDS = ("version", "name", "value", "port", "port_specified", "domain", "domain_specified",
                 "domain_initial_dot", "path", "path_specified", "secure", "expires", "discard",
                 "comment", "comment_url", "rfc2109")


class DuPanError(Exception):
    """Only fixed text and validated numeric codes may appear in this exception."""


def create_htj_token(cuid, user_agent):
    """Run the official Sofire web SDK in Node/jsdom, without App or browser."""
    script = Path(__file__).with_name("dupan_htj.js")
    if not script.is_file():
        raise DuPanError("缺少纯脚本 HTJ 生成器，未发送领奖请求。")
    payload = {"cuid": cuid, "userAgent": user_agent,
               "proxy": os.getenv("SIGN_HTJ_PROXY_DUPAN") or None}
    environment = {key: os.environ[key] for key in ("PATH", "NODE_PATH") if key in os.environ}
    try:
        result = subprocess.run(["node", str(script)], input=json.dumps(payload), text=True,
                                capture_output=True, timeout=30, env=environment, check=False)
        data = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        data = None
    if (not isinstance(data, dict) or not isinstance(data.get("jt"), str) or
            not 0 < len(data["jt"]) <= 20000 or
            not isinstance(data.get("version"), str) or
            not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", data["version"])):
        raise DuPanError("纯脚本 HTJ 生成失败，未发送领奖请求。")
    return data


def number(value):
    if type(value) is int or isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,18}", value):
        return int(value)
    raise DuPanError("服务端状态字段无效，停止本轮。")


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DuPanError("私有配置或状态文件无法读取，停止本轮。") from None


def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def write_json(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix=".dupan-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def state_directory():
    default = Path("/ql/data/dupan") if Path("/ql/data").is_dir() else Path(__file__).resolve().parent / "data/dupan"
    return Path(os.getenv("SIGN_STATE_DIR_DUPAN") or default).expanduser().resolve()


@contextmanager
def directory_lock(directory):
    private_dir(directory)
    descriptor = os.open(str(directory / "run.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DuPanError("已有百度签到进程运行，当前任务停止。") from None
        yield


def parse_cookie(raw):
    if not isinstance(raw, str) or re.search(r"[\r\n\x00]", raw) or len(raw) > 65536:
        raise DuPanError("Cookie 格式无效。")
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    cookies = {}
    for part in value.split(";"):
        key, separator, content = part.strip().partition("=")
        if separator:
            if not re.fullmatch(r"[!#$%&'*+.^_\x60|~0-9A-Za-z-]+", key):
                raise DuPanError("Cookie 名称格式无效。")
            cookies[key] = content
    if not (cookies.get("BDUSS") or cookies.get("BDUSS_BFESS")):
        raise DuPanError("Cookie 缺少 BDUSS/BDUSS_BFESS 登录凭证。")
    return cookies


def validate_profile(data):
    if not isinstance(data, dict) or data.get("origin") != ORIGIN:
        raise DuPanError("登录资料必须属于百度网盘官方 HTTPS 域名。")
    static, ua = data.get("native_static_params"), data.get("user_agent")
    if (not isinstance(static, dict) or set(static) != STATIC_KEYS or
            any(not isinstance(v, str) or not v or len(v) > 2048 or re.search(r"[\r\n\x00]", v)
                for v in static.values())):
        raise DuPanError("S1 需要已验证的 8 个静态客户端字段；请导入完整登录资料。")
    if not isinstance(ua, str) or not ua or len(ua) > 2048 or re.search(r"[\r\n\x00]", ua):
        raise DuPanError("缺少已验证的 User-Agent。")
    cookies = parse_cookie(data.get("cookie"))
    return {"origin": ORIGIN, "native_static_params": dict(static), "user_agent": ua,
            "cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}


def import_profile(source, directory):
    profile = validate_profile(read_json(source))
    with directory_lock(directory):
        destination = directory / "auth.json"
        if destination.exists():
            raise DuPanError("本地登录资料已存在；未覆盖，请通过 SIGN_AUTH_DUPAN 选择新资料。")
        write_json(destination, profile)
    return destination


class DuPanSign(BaseSign):
    retry_times = 1
    LOGIN = "/api/loginstatus"
    HOME = "/coins/taskcenter/home"
    TASKS = "/coins/taskcenter/tasklist"
    SIGN = "/coins/taskcenter/signin"
    SIGN_LIST = "/coins/taskcenter/signinlist"
    USER = "/rest/2.0/membership/user"
    QUESTION = "/act/v2/membergrowv2/getdailyquestion"
    ANSWER = "/act/v2/membergrowv2/answerquestion"
    GROWTH_TASKS = "/api/taskscore/tasklist"
    REPORT = "/api/taskscore/tasksave"
    CLAIM = "/api/taskscore/antisave"
    BUSINESS_KEYS = {"task_id", "task_id_str", "task_from", "is_growth"}
    MUTATIONS = {SIGN, ANSWER, REPORT, CLAIM}

    def __init__(self, read_only=False, include_answer=False, claim_probe=False):
        # Preserve BaseSign logging/notification integration; no password is used.
        overrides = {"SIGN_UP_DUPAN": "cookie-user|cookie-auth", "SIGN_URL_DUPAN": ORIGIN}
        previous = {key: os.environ.get(key) for key in overrides}
        os.environ.update(overrides)
        try:
            super().__init__(ORIGIN, app_name="百度网盘任务中心签到", app_key="DUPAN")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        # The mutation is GET: override BaseSign's automatic HTTP retries.
        self.session.mount("https://", HTTPAdapter(max_retries=0))
        self.session.mount("http://", HTTPAdapter(max_retries=0))
        self.session.trust_env = False
        self.session.verify = True
        self.session.headers.clear()
        self.session.headers.update({"Accept": "application/json, text/plain, */*",
                                     "X-Requested-With": "XMLHttpRequest",
                                     "Referer": ORIGIN + "/operation/activitys/taskSystem/growth"})
        self.exec_method = ["sign"]
        self.read_only = read_only
        self.include_answer = include_answer
        self.claim_probe = claim_probe
        self.directory = state_directory()
        self.report = {"started_at": datetime.now(timezone.utc).isoformat(),
                       "profile": "claim_probe" if claim_probe else "S1",
                       "read_only": read_only, "success": False, "requests": []}
        self.source_digest = None
        self.ledger = None
        self.question_ledger = None
        self.mutation_count = 0
        self.mutation_counts = {}
        self.session_ready = False
        self.locked = False
        self.claim_security = None
        self.sofire_material = None
        self.sofire_extras = None
        self.claim_authorized = False

    def _load_session(self):
        source = Path(os.getenv("SIGN_AUTH_DUPAN") or self.directory / "auth.json").expanduser()
        profile = read_json(source) if source.is_file() else {}
        if os.getenv("SIGN_AUTH_DUPAN") and not source.is_file():
            raise DuPanError("SIGN_AUTH_DUPAN 指定的登录资料不存在。")
        if not isinstance(profile, dict):
            raise DuPanError("登录资料格式无效。")
        if os.getenv("SIGN_COOKIE_DUPAN"):
            profile = {**profile, "origin": ORIGIN, "cookie": os.environ["SIGN_COOKIE_DUPAN"]}
        if os.getenv("SIGN_CLIENT_DUPAN"):
            try:
                profile["native_static_params"] = json.loads(os.environ["SIGN_CLIENT_DUPAN"])
            except ValueError:
                raise DuPanError("SIGN_CLIENT_DUPAN 必须是静态客户端字段 JSON。") from None
        if os.getenv("SIGN_USER_AGENT_DUPAN"):
            profile["user_agent"] = os.environ["SIGN_USER_AGENT_DUPAN"]
        self.profile = validate_profile(profile)
        self.source_digest = hashlib.sha256(json.dumps(self.profile, sort_keys=True).encode()).hexdigest()
        self.session.headers["User-Agent"] = self.profile["user_agent"]
        self.session.cookies = CookieJar()
        saved_path = self.directory / "session.json"
        saved = read_json(saved_path) if saved_path.exists() else {}
        if saved.get("source_digest") == self.source_digest:
            records = saved.get("cookies")
            if not isinstance(records, list):
                raise DuPanError("保存的 CookieJar 格式无效。")
            for record in records:
                cookie = Cookie(**record)
                if cookie.domain.lstrip(".") not in {"baidu.com", "pan.baidu.com"}:
                    raise DuPanError("保存的 Cookie 域名无效。")
                self.session.cookies.set_cookie(cookie)
        else:
            for key, value in parse_cookie(self.profile["cookie"]).items():
                self.session.cookies.set_cookie(Cookie(0, key, value, None, False, "pan.baidu.com",
                                                       False, False, "/", True, True, None, True,
                                                       None, None, {}, False))
        self.session_ready = True

    def _persist(self):
        records = []
        for cookie in self.session.cookies:
            if cookie.domain.lstrip(".") in {"baidu.com", "pan.baidu.com"}:
                records.append({**{key: getattr(cookie, key) for key in COOKIE_FIELDS},
                                "rest": dict(cookie._rest)})
        write_json(self.directory / "session.json", {"source_digest": self.source_digest,
                   "cookies": records, "updated_at": datetime.now(timezone.utc).isoformat()})

    def _request_json(self, path, extra=None):
        extra = extra or {}
        permitted = {self.LOGIN: set(), self.HOME: set(), self.TASKS: {"task_from"},
                     self.SIGN: self.BUSINESS_KEYS, self.SIGN_LIST: self.BUSINESS_KEYS,
                     self.USER: {"method"}, self.QUESTION: set(),
                     self.ANSWER: {"ask_id", "answer"},
                     self.GROWTH_TASKS: {"task_from"},
                     self.REPORT: {"task_id", "task_from", "uk"},
                     self.CLAIM: {"task_ids", "task_froms", "uk", "action"}}
        if path not in permitted or set(extra) != permitted[path]:
            raise DuPanError("拒绝访问签到白名单之外的接口或参数。")
        if path == self.CLAIM and (not self.claim_authorized or self.claim_security is None or
                                   self.sofire_material is None or self.sofire_extras is None or
                                   extra["action"] != "receive_award"):
            raise DuPanError("纯脚本领奖尚未完成一次性预检。")
        if path == self.CLAIM and datetime.now(SHANGHAI).date().isoformat() != self.report.get("answer", {}).get("day"):
            raise DuPanError("领奖实验预检期间发生换日，未发送请求。")
        if path in self.MUTATIONS and (self.read_only or not self.locked or self.mutation_counts.get(path)):
            raise DuPanError("当前运行不允许再次提交该任务动作。")
        htj = create_htj_token(self.profile["native_static_params"]["cuid"],
                               self.profile["user_agent"]) if path == self.CLAIM else None
        params = {**self.profile["native_static_params"], **extra,
                  "rand": secrets.token_hex(20), "time": str(int(time.time()))}
        if path == self.CLAIM:
            bduss = next((cookie.value for cookie in self.session.cookies
                          if cookie.name == "BDUSS" and cookie.domain.lstrip(".") in {"baidu.com", "pan.baidu.com"}), None)
            if not bduss:
                raise DuPanError("领奖签名缺少当前 BDUSS，停止本轮。")
            security = self.claim_security
            static = self.profile["native_static_params"]
            try:
                params["rand"], params["rand2"] = native_rand_pair(
                    bduss, security["uid"], security["encrypted_sk"], params["time"],
                    static["devuid"], static["version"])
                params["rchannel"] = native_rchannel(security["uid"], params["time"], static["channel"])
                params["z"] = sofire_z(**self.sofire_material, timestamp=params["time"])
            except ValueError:
                raise DuPanError("领奖签名资料无效，未发送请求。") from None
            params.update({"jt": htj["jt"], "aid": "13655", "ev": "task", "hjs": 1,
                           "c": static["cuid"], "ver": static["version"],
                           "ua": self.profile["user_agent"].lower(),
                           "offlinepackage": json.dumps(self.sofire_extras["offlinepackage"],
                                                        ensure_ascii=False, separators=(",", ":")),
                           "themeinfo": self.sofire_extras["themeinfo"]})
            self.report["htj_sdk_version"] = htj["version"]
        if path in {self.REPORT, self.CLAIM}:
            identifier = params["task_id"] if path == self.REPORT else params["task_ids"]
            payload = "_".join((str(identifier), str(params["uk"]), params["rand"],
                                params["time"], TASK_TOKEN_SALT))
            params["token"] = hashlib.md5(payload.encode()).hexdigest()
        entry = {"path": path, "query_keys": sorted(params), "mutation": path in self.MUTATIONS,
                 "at": datetime.now(timezone.utc).isoformat()}
        if path in self.MUTATIONS:
            self.mutation_count += 1
            self.mutation_counts[path] = self.mutation_counts.get(path, 0) + 1
        self.report["requests"].append(entry)
        try:
            with self.session.get(ORIGIN + path, params=params, timeout=25,
                                  allow_redirects=False, stream=True) as response:
                entry["http_status"] = response.status_code
                if response.status_code != 200:
                    raise DuPanError(f"接口 HTTP {response.status_code}，停止且不重试。")
                payload = bytearray()
                for chunk in response.iter_content(65536):
                    payload.extend(chunk)
                    if len(payload) > 2 * 1024 * 1024:
                        raise DuPanError("响应超过大小限制。")
                data = json.loads(payload)
        except DuPanError:
            raise
        except Exception:
            entry["transport_or_decode_error"] = True
            raise DuPanError("HTTP 请求失败或响应无效，未自动重试。") from None
        if not isinstance(data, dict):
            raise DuPanError("接口响应不是对象。")
        code = number(data.get("errno", data.get("error_code")))
        entry["business_code"] = code
        self.pwl(f"{path}：HTTP 200，业务码 {code}")
        if code != 0:
            raise DuPanError(f"百度业务码 {code}，凭证失效或请求被拒绝，停止本轮。")
        return data

    def login(self):
        self._load_session()
        data = self._request_json(self.LOGIN).get("login_info", {})
        uk = data.get("uk_str")
        if not isinstance(uk, str) or not re.fullmatch(r"[0-9]{1,24}", uk):
            raise DuPanError("未读到有效登录身份，停止签到。")
        account = hashlib.sha256(uk.encode()).hexdigest()
        self.uk = uk
        self.ledger_path = self.directory / ("attempt-" + account + ".json")
        self.ledger = read_json(self.ledger_path) if self.ledger_path.exists() else {}
        self.question_ledger_path = self.directory / ("question-" + account + ".json")
        self.question_ledger = read_json(self.question_ledger_path) if self.question_ledger_path.exists() else {}
        return True

    def _home(self):
        data = self._request_json(self.HOME).get("data", {})
        signed = number(data.get("signed"))
        if signed not in {0, 1}:
            raise DuPanError("当天签到状态不明确，停止本轮。")
        return {"signed": signed, "points": number(data.get("points_balance")),
                "signin_days": number(data.get("signin_days"))}

    def _task(self):
        data = self._request_json(self.TASKS, {"task_from": "task_sys_daily"})
        tasks = data.get("result", {}).get("list")
        if not isinstance(tasks, list):
            raise DuPanError("签到任务列表无效。")
        tasks = [task for task in tasks if isinstance(task, dict) and str(task.get("task_type")) == "166"]
        if len(tasks) != 1:
            raise DuPanError("签到任务不存在或不唯一。")
        task = tasks[0]
        identifier = task.get("task_id_str")
        if (task.get("task_from") != "task_sys_daily" or not isinstance(identifier, str)
                or not re.fullmatch(r"[0-9]{1,24}", identifier)):
            raise DuPanError("签到任务来源或字符串 ID 无效。")
        return {"task_id": identifier, "task_id_str": identifier,
                "task_from": "task_sys_daily", "is_growth": "1"}

    def _readback(self, task, home=None, target=None):
        state = target if target is not None else {}
        state.update(home if home is not None else self._home())
        data = self._request_json(self.SIGN_LIST, task).get("data", {})
        state.update(signed_today=number(data.get("signed_today")),
                     list_signin_days=number(data.get("signin_days")), server_time=number(data.get("date")))
        server = datetime.fromtimestamp(state["server_time"], SHANGHAI)
        if abs(server.timestamp() - time.time()) > 300:
            raise DuPanError("服务端签到日期与当前时间不一致，停止本轮。")
        state["server_day"] = server.date().isoformat()
        member = self._request_json(self.USER, {"method": "query"})
        state["growth"] = number(member.get("level_info", {}).get("current_value"))
        if state["signed"] != state["signed_today"] or state["signin_days"] != state["list_signin_days"]:
            raise DuPanError("两处签到状态或连续天数不一致，停止本轮。")
        return state

    def sign(self):
        home = self._home()
        self.report["before"] = dict(home)
        if home["signed"]:
            self.report["status"] = "already_signed"
            self.pwl(f"今日已签到，连续 {home['signin_days']} 天，积分 {home['points']}；本次提交 0 次。")
            return True
        task = self._task()
        before = self._readback(task, home, self.report["before"])
        self.report["task"] = {"task_type": 166, **task}
        if self.read_only:
            self.report["status"] = "unsigned_read_only"
            self.pwl("今日未签到，只读模式不提交。")
            return True
        day = before["server_day"]
        if self.ledger.get("day") == day:
            raise DuPanError("当天已有提交记录；仅保留状态读回，不重复签到。")
        if datetime.now(SHANGHAI).date().isoformat() != day:
            raise DuPanError("预检期间发生换日，请重新读取状态。")
        self.ledger = {"day": day, "status": "attempting", "task_id_str": task["task_id_str"],
                       "at": datetime.now(timezone.utc).isoformat()}
        write_json(self.ledger_path, self.ledger)  # Persist BEFORE sending, including process crashes.
        error = None
        try:
            self._request_json(self.SIGN, task)
        except DuPanError as exc:
            error = str(exc)
        after = self.report["after"] = {}
        try:
            self._readback(task, target=after)
            self.report["delta"] = {key: after[key] - before[key] for key in ("points", "growth", "signin_days")}
            confirmed = (after["server_day"] == day and after["signed"] == 1 and after["signed_today"] == 1
                         and after["signin_days"] == before["signin_days"] + 1)
        except DuPanError as exc:
            confirmed = False
            self.report["readback_error"] = str(exc)
        success = confirmed and error is None
        self.report["status"] = "signed" if success else "submission_needs_review"
        if error:
            self.report["submission_error"] = error
        self.ledger["status"] = self.report["status"]
        write_json(self.ledger_path, self.ledger)
        if not success:
            self.pwl("签到提交后结果需要核对；已保存只读证据，当天不会自动重试。")
            return False
        delta = self.report["delta"]
        self.pwl(f"任务中心签到成功：连续 {after['signin_days']} 天，积分 +{delta['points']}，成长值 +{delta['growth']}。")
        return True

    def _question(self):
        data = self._request_json(self.QUESTION).get("data")
        if not isinstance(data, dict):
            raise DuPanError("每日题目状态无效。")
        status = number(data.get("answer_status"))
        if status not in {-1, 0, 1}:
            raise DuPanError("每日答题状态不明确。")
        ask_id = str(data.get("ask_id", ""))
        if not re.fullmatch(r"[0-9]{1,24}", ask_id):
            raise DuPanError("每日题目 ID 无效。")
        ask_time = number(data.get("ask_time"))
        day = datetime.fromtimestamp(ask_time, SHANGHAI).date().isoformat()
        if day != datetime.now(SHANGHAI).date().isoformat():
            raise DuPanError("题目日期与当前日期不一致，停止本轮。")
        answer = number(data.get("answer")) if status == -1 else None
        if status == -1 and answer not in {0, 1}:
            raise DuPanError("题目不是已验证的判断题格式。")
        return {"status": status, "ask_id": ask_id, "answer": answer, "day": day}

    def _growth_task(self):
        data = self._request_json(self.GROWTH_TASKS, {"task_from": "task_sys_task_growth"})
        tasks = data.get("result", {}).get("list")
        if not isinstance(tasks, list):
            raise DuPanError("成长任务列表无效。")
        matches = [task for task in tasks if isinstance(task, dict) and str(task.get("task_type")) == "169"]
        if len(matches) != 1:
            raise DuPanError("每日答题任务不存在或不唯一。")
        task = matches[0]
        identifier = task.get("task_id_str")
        if (task.get("task_from") != "task_sys_task_growth" or not isinstance(identifier, str)
                or not re.fullmatch(r"[0-9]{1,24}", identifier)):
            raise DuPanError("每日答题任务来源或字符串 ID 无效。")
        status = number(task.get("task_status"))
        if status not in {0, 1, 3, 6}:
            raise DuPanError("每日答题任务状态不明确。")
        return {"task_id": identifier, "task_from": "task_sys_task_growth", "status": status}

    def _balances(self):
        home = self._home()
        member = self._request_json(self.USER, {"method": "query"})
        return {"signed": home["signed"], "points": home["points"],
                "growth": number(member.get("level_info", {}).get("current_value"))}

    def _save_question_attempt(self, question, task, action):
        if datetime.now(SHANGHAI).date().isoformat() != question["day"]:
            raise DuPanError("答题预检期间发生换日，停止本轮。")
        ledger = self.question_ledger
        if ledger.get("day") == question["day"]:
            if ledger.get("ask_id") != question["ask_id"] or ledger.get("task_id_str") != task["task_id"]:
                raise DuPanError("当天题目或任务 ID 已变化，停止本轮。")
        else:
            ledger = {"day": question["day"], "ask_id": question["ask_id"],
                      "task_id_str": task["task_id"]}
        if action in ledger:
            raise DuPanError("当天已尝试该答题动作；仅保留状态读回，不重复提交。")
        ledger[action] = {"status": "attempting", "at": datetime.now(timezone.utc).isoformat()}
        write_json(self.question_ledger_path, ledger)
        self.question_ledger = ledger

    def answer(self):
        question, task = self._question(), self._growth_task()
        result = self.report["answer"] = {"day": question["day"], "question_status": question["status"],
                                          "task_status": task["status"]}
        if self.question_ledger.get("day") == question["day"] and (
                self.question_ledger.get("ask_id") != question["ask_id"] or
                self.question_ledger.get("task_id_str") != task["task_id"]):
            raise DuPanError("当天题目或任务 ID 已变化，停止本轮。")
        if self.read_only:
            result["status"] = "read_only"
            self.pwl(f"每日答题只读：题目状态 {question['status']}，任务状态 {task['status']}。")
            return True
        if question["status"] == 0:
            result["status"] = "answered_wrong"
            self.pwl("每日题目已答错，停止上报。")
            return False
        if task["status"] == 1:
            if question["status"] != 1:
                raise DuPanError("题目与任务完成状态不一致。")
            result["status"] = "already_claimed"
            self.pwl("每日答题任务已完成并领取，本次提交 0 次。")
            return True
        if question["status"] == -1:
            if task["status"] not in {0, 3}:
                raise DuPanError("题目未答但任务已待领取，停止本轮。")
            self._save_question_attempt(question, task, "answer")
            try:
                response = self._request_json(self.ANSWER, {"ask_id": question["ask_id"],
                                                           "answer": question["answer"]})
                answer_data = response.get("data")
                if not isinstance(answer_data, dict) or number(answer_data.get("answer_status")) != 1:
                    raise DuPanError("答题提交未确认正确。")
            except DuPanError as exc:
                result["submission_error"] = str(exc)
            after_question = self._question()
            result["question_status"] = after_question["status"]
            if after_question["ask_id"] != question["ask_id"] or after_question["status"] != 1 or "submission_error" in result:
                result["status"] = "answer_needs_review"
                self.pwl("答题提交结果待核对；当天不会自动重试或继续上报。")
                return False
        task_after_answer = self._growth_task()
        if task_after_answer["task_id"] != task["task_id"]:
            raise DuPanError("答题任务 ID 在执行中变化，停止本轮。")
        task = task_after_answer
        if task["status"] in {0, 3}:
            before = self._balances()
            self._save_question_attempt(question, task, "report")
            try:
                self._request_json(self.REPORT, {"task_id": task["task_id"],
                                                 "task_from": task["task_from"], "uk": self.uk})
            except DuPanError as exc:
                result["report_error"] = str(exc)
            after_task = self._growth_task()
            result["task_status"] = after_task["status"]
            if after_task["task_id"] != task["task_id"] or after_task["status"] not in {1, 6} or "report_error" in result:
                result["status"] = "report_needs_review"
                self.pwl("答题任务上报结果待核对；当天不会自动重试。")
                return False
            after = self._balances()
            result["balance_delta"] = {key: after[key] - before[key] for key in ("points", "growth")}
            task = after_task
        if task["status"] == 6:
            prior_attempt = (self.question_ledger.get("day") == question["day"] and
                             ("claim" in self.question_ledger or "claim_probe" in self.question_ledger))
            try:
                return self._claim_reward(self._question(), task, result, "claim")
            except DuPanError as exc:
                result["status"] = ("claim_skipped_prior_attempt" if prior_attempt else
                                    "claim_needs_review" if "claim" in self.question_ledger else
                                    "claim_preflight_failed")
                result["claim_error"] = str(exc)
                self.pwl("每日答题领奖未确认；当天不会自动重试。")
                return False
        result["status"] = "already_claimed"
        self.pwl("每日答题任务已完成并领取。")
        return True

    def _load_claim_security(self):
        source = self.directory / "claim-signing.json"
        if source.is_symlink() or not source.is_file() or source.stat().st_mode & 0o077:
            raise DuPanError("一次性领奖实验需要私有签名资料文件（0600）。")
        security = read_json(source)
        if (not isinstance(security, dict) or set(security) != {"uid", "encrypted_sk", "account_uk_sha256"} or
                security["account_uk_sha256"] != hashlib.sha256(self.uk.encode()).hexdigest() or
                not isinstance(security["uid"], str) or not re.fullmatch(r"[0-9]{1,24}", security["uid"]) or
                not isinstance(security["encrypted_sk"], str)):
            raise DuPanError("领奖签名资料与当前账号不匹配，未发送请求。")
        bduss = next((cookie.value for cookie in self.session.cookies
                      if cookie.name == "BDUSS" and cookie.domain.lstrip(".") in {"baidu.com", "pan.baidu.com"}), None)
        static = self.profile["native_static_params"]
        try:
            native_rand_pair(bduss, security["uid"], security["encrypted_sk"],
                             str(int(time.time())), static["devuid"], static["version"])
        except ValueError:
            raise DuPanError("领奖签名资料无效，未发送请求。") from None
        self.claim_security = security
        source = self.directory / "sofire-material.json"
        if source.is_symlink() or not source.is_file() or source.stat().st_mode & 0o077:
            raise DuPanError("纯脚本领奖需要私有 Sofire 材料文件（0600）。")
        material = read_json(source)
        static = self.profile["native_static_params"]
        if (not isinstance(material, dict) or
                set(material) != {"seed", "status", "flag1", "flag2", "flag3",
                                  "account_uk_sha256", "cuid_sha256", "version",
                                  "offlinepackage", "themeinfo"} or
                material["account_uk_sha256"] != security["account_uk_sha256"] or
                material["cuid_sha256"] != hashlib.sha256(static["cuid"].encode()).hexdigest() or
                material["version"] != static["version"] or
                not isinstance(material["offlinepackage"], dict) or
                not 1 <= len(material["offlinepackage"]) <= 128 or
                type(material["themeinfo"]) is not int or
                not 0 <= material["themeinfo"] <= 1000000000):
            raise DuPanError("Sofire 材料与账号或设备不匹配，未发送请求。")
        try:
            package = json.dumps(material["offlinepackage"], ensure_ascii=False,
                                 separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError):
            raise DuPanError("客户端包资料格式无效，未发送请求。") from None
        if len(package) > 4096:
            raise DuPanError("客户端包资料过长，未发送请求。")
        self.sofire_material = {key: material[key] for key in
                                ("seed", "status", "flag1", "flag2", "flag3")}
        self.sofire_extras = {key: material[key] for key in ("offlinepackage", "themeinfo")}
        try:
            sofire_z(**self.sofire_material, timestamp=str(int(time.time())))
        except ValueError:
            raise DuPanError("Sofire 材料无效，未发送请求。") from None

    def claim_reward_probe(self):
        """Manual no-App claim check, sharing the daily once-only ledger."""
        if not self.claim_probe or self.read_only:
            raise DuPanError("当前模式禁止领奖实验。")
        question, task = self._question(), self._growth_task()
        result = self.report["answer"] = {"day": question["day"], "question_status": question["status"],
                                          "task_status": task["status"], "probe": True}
        if question["status"] != 1:
            raise DuPanError("题目尚未确认答对，不尝试领奖。")
        if task["status"] == 1:
            result["status"] = "already_claimed_no_probe"
            self.pwl("答题奖励已被领取，无法验证这次纯脚本实验。")
            return False
        return self._claim_reward(question, task, result, "claim_probe")

    def _claim_reward(self, question, task, result, action):
        """Submit at most once per day, then verify the same task and balances."""
        if self.read_only or action not in {"claim", "claim_probe"}:
            raise DuPanError("当前模式禁止领取答题奖励。")
        result["day"] = question["day"]
        result["question_status"] = question["status"]
        result["task_status"] = task["status"]
        if question["status"] != 1:
            raise DuPanError("题目尚未确认答对，不尝试领奖。")
        if task["status"] != 6 or self._home()["signed"] != 1:
            raise DuPanError("答题任务不在当天已签到、待领取状态。")
        if (self.question_ledger.get("day") == question["day"] and
                (self.question_ledger.get("ask_id") != question["ask_id"] or
                 self.question_ledger.get("task_id_str") != task["task_id"])):
            raise DuPanError("当天题目或任务 ID 已变化，停止领奖实验。")
        if self.question_ledger.get("day") == question["day"] and (
                "claim" in self.question_ledger or "claim_probe" in self.question_ledger):
            raise DuPanError("当天已尝试领奖，不重复生成 HTJ 或提交请求。")
        self._load_claim_security()
        before = self._balances()
        self._save_question_attempt(question, task, action)
        response, error = None, None
        try:
            self.claim_authorized = True
            response = self._request_json(self.CLAIM, {"task_ids": task["task_id"],
                "task_froms": task["task_from"], "uk": self.uk, "action": "receive_award"})
        except DuPanError as exc:
            error = str(exc)
        finally:
            self.claim_authorized = False
        after_task = self._growth_task()
        after = self._balances()
        result["task_status"] = after_task["status"]
        if "balance_delta" in result:
            result["report_balance_delta"] = result.pop("balance_delta")
        result["balance_delta"] = {key: after[key] - before[key] for key in ("points", "growth")}
        if error:
            result["submission_error"] = error
        if after_task["task_id"] != task["task_id"] or after_task["status"] != 1 or error:
            result["status"] = "claim_needs_review"
            self.pwl("纯脚本领奖未确认成功；当天不会自动重试。")
            return False
        reward = response.get("result") if isinstance(response, dict) else None
        result["reward_response_shape"] = {
            "top_keys": sorted(response) if isinstance(response, dict) else [],
            "result_type": type(reward).__name__,
            "data_type": type(response.get("data")).__name__ if isinstance(response, dict) else "NoneType"}
        for source in ("result", "data"):
            candidate = response.get(source) if isinstance(response, dict) else None
            if isinstance(candidate, list) and len(candidate) == 1:
                candidate = candidate[0]
            if isinstance(candidate, dict) and {"addScore", "addGrowScore"} <= candidate.keys():
                expected = {"points": number(candidate["addScore"]),
                            "growth": number(candidate["addGrowScore"])}
                result["reward_response"] = expected
                result["reward_response_source"] = source
                if expected != result["balance_delta"]:
                    result["status"] = "claim_needs_review"
                    self.pwl("领奖响应与到账增量不一致；当天不会自动重试。")
                    return False
                break
        delta = result["balance_delta"]
        if min(delta.values()) < 0 or sum(delta.values()) <= 0:
            result["status"] = "claim_needs_review"
            self.pwl("领奖后余额未确认增加；当天不会自动重试。")
            return False
        result["status"] = "claimed" if "reward_response" in result else "claimed_readback_only"
        self.pwl("纯脚本领奖已读回到账。" if "reward_response" in result else
                 "纯脚本领奖已读回到账；响应未提供可核对的奖励明细。")
        return True

    def _exec(self, content):
        # Keep one lock through requests, submission ledger and CookieJar persistence.
        try:
            with directory_lock(self.directory):
                self.locked = True
                try:
                    if self.claim_probe:
                        self.sign_success = bool(self.login())
                        self.answer_success = self.claim_reward_probe() if self.sign_success else None
                    else:
                        self.sign_success = bool(self.login() and self.sign())
                        self.answer_success = self.answer() if self.sign_success and self.include_answer else None
                    self.last_run_success = self.sign_success and self.answer_success is not False
                except Exception as exc:
                    self.last_run_success = False
                    self.report["error"] = str(exc) if isinstance(exc, DuPanError) else "本地状态或响应格式无效。"
                    self.pwl(self.report["error"])
                finally:
                    if self.session_ready:
                        try:
                            self._persist()
                        except Exception:
                            self.last_run_success = False
                            self.report["credential_save_failed"] = True
                            self.pwl("刷新后的 Cookie 保存失败。")
                    self.report.update(success=self.last_run_success, mutation_request_count=self.mutation_count,
                                       finished_at=datetime.now(timezone.utc).isoformat())
                    reports = private_dir(self.directory / "reports")
                    identifier = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(4)
                    write_json(reports / (identifier + ".json"), self.report)
        except Exception as exc:
            self.last_run_success = False
            self.pwl(str(exc) if isinstance(exc, DuPanError) else "本地状态或报告保存失败，停止本轮。")
        finally:
            self.locked = False
        if self.claim_probe:
            return content + f"一次性答题领奖实验：{getattr(self, 'answer_success', None)}\n" + self.log()
        return content + f"任务中心签到结果：{getattr(self, 'sign_success', False)}；答题任务完成：{getattr(self, 'answer_success', None)}\n" + self.log()


def main(argv=None):
    parser = argparse.ArgumentParser(description="百度网盘任务中心纯脚本签到及每日答题")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--status", action="store_true", help="只读签到与答题状态，禁止提交，不发送通知")
    modes.add_argument("--import-auth", type=Path, help="离线导入已有登录资料，不请求网络，不覆盖已有文件")
    modes.add_argument("--claim-probe", action="store_true", help="一次性无 App 领奖实验；不属于每日定时任务")
    parser.add_argument("--no-notify", action="store_true", help="只在控制台输出，不发送通知")
    parser.add_argument("--sign-only", action="store_true", help="仅运行已验证的签到，不执行每日答题")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.import_auth:
            destination = import_profile(args.import_auth, state_directory())
            print(f"登录资料已保存（0600）：{destination}")
            return 0
        sign = DuPanSign(read_only=args.status, include_answer=not args.sign_only,
                         claim_probe=args.claim_probe)
        if args.status or args.no_notify or args.claim_probe:
            sign._exec("")
        else:
            sign.run()
        return 0 if sign.last_run_success else 1
    except Exception as exc:
        print(str(exc) if isinstance(exc, DuPanError) else "百度签到未完成；请检查脱敏日志。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
