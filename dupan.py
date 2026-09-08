# -*- coding:utf-8 -*-
"""
cron: 0 20 8 * * *
new Env('百度网盘任务中心签到');

SIGN_AUTH_DUPAN: 私有登录资料 JSON（兼容 one-tap-capture 格式）。
或 SIGN_COOKIE_DUPAN + SIGN_CLIENT_DUPAN（静态字段 JSON）+ SIGN_USER_AGENT_DUPAN。
SIGN_STATE_DIR_DUPAN: 持久目录，青龙默认 /ql/data/dupan，本地默认 data/dupan。
仅执行已验证的 S1 签到，不执行旧会员签到、答题或领奖。
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
import sys
import tempfile
import time

from requests.adapters import HTTPAdapter

from base import BaseSign


ORIGIN = "https://pan.baidu.com"
SHANGHAI = timezone(timedelta(hours=8))
STATIC_KEYS = {"app", "channel", "clienttype", "cuid", "devuid", "rchannel", "version", "versioncode"}
COOKIE_FIELDS = ("version", "name", "value", "port", "port_specified", "domain", "domain_specified",
                 "domain_initial_dot", "path", "path_specified", "secure", "expires", "discard",
                 "comment", "comment_url", "rfc2109")


class DuPanError(Exception):
    """Only fixed text and validated numeric codes may appear in this exception."""


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
    BUSINESS_KEYS = {"task_id", "task_id_str", "task_from", "is_growth"}

    def __init__(self, read_only=False):
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
        self.directory = state_directory()
        self.report = {"started_at": datetime.now(timezone.utc).isoformat(), "profile": "S1",
                       "read_only": read_only, "success": False, "requests": []}
        self.source_digest = None
        self.ledger = None
        self.mutation_count = 0
        self.session_ready = False
        self.locked = False

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
                     self.USER: {"method"}}
        if path not in permitted or set(extra) != permitted[path]:
            raise DuPanError("拒绝访问签到白名单之外的接口或参数。")
        if path == self.SIGN and (self.read_only or not self.locked or self.mutation_count):
            raise DuPanError("当前运行不允许再次提交签到。")
        params = {**self.profile["native_static_params"], **extra,
                  "rand": secrets.token_hex(20), "time": str(int(time.time()))}
        entry = {"path": path, "query_keys": sorted(params), "mutation": path == self.SIGN,
                 "at": datetime.now(timezone.utc).isoformat()}
        if path == self.SIGN:
            self.mutation_count += 1
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
        self.ledger_path = self.directory / ("attempt-" + account + ".json")
        self.ledger = read_json(self.ledger_path) if self.ledger_path.exists() else {}
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

    def _exec(self, content):
        # Keep one lock through requests, submission ledger and CookieJar persistence.
        try:
            with directory_lock(self.directory):
                self.locked = True
                try:
                    self.last_run_success = bool(self.login() and self.sign())
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
        return content + f"任务中心签到结果：{self.last_run_success}\n" + self.log()


def main(argv=None):
    parser = argparse.ArgumentParser(description="百度网盘任务中心纯脚本签到（S1）")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--status", action="store_true", help="只读登录和签到状态，禁止提交，不发送通知")
    modes.add_argument("--import-auth", type=Path, help="离线导入已有登录资料，不请求网络，不覆盖已有文件")
    parser.add_argument("--no-notify", action="store_true", help="只在控制台输出，不发送通知")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.import_auth:
            destination = import_profile(args.import_auth, state_directory())
            print(f"登录资料已保存（0600）：{destination}")
            return 0
        sign = DuPanSign(read_only=args.status)
        if args.status or args.no_notify:
            sign._exec("")
        else:
            sign.run()
        return 0 if sign.last_run_success else 1
    except Exception as exc:
        print(str(exc) if isinstance(exc, DuPanError) else "百度签到未完成；请检查脱敏日志。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
