# 百度网盘 App 任务中心签到

`dupan.py` 对应 App「我的 → 用户名旁 VIP → 成长值任务 / 去签到 → 任务中心」签到。
唯一变更接口是 `GET https://pan.baidu.com/coins/taskcenter/signin`。
已移除旧 `/rest/2.0/membership/level?method=signin`、每日答题和领奖流程。

## 验证范围

2026-09-08，来源项目 one-tap-capture 的纯 Python S1 入口使用下列参数成功完成一次首次签到：

| 项目 | 已验证输入 / 结果 |
|---|---|
| 凭证 | 完整 Cookie；本轮没有验证 Cookie 缩减 |
| 静态客户端 | `app/channel/clienttype/cuid/devuid/rchannel/version/versioncode`，全部保留已验证值 |
| 请求头 | 已验证的 User-Agent、Referer、Accept、X-Requested-With |
| 业务参数 | 当前查询的 `task_type=166` 对应 `task_id_str`，同时作为 `task_id`；`task_from=task_sys_daily`、`is_growth=1` |
| 动态参数 | 每次本地生成 `rand/time` |
| 不发送 | `z/rand2/offlinepackage/themeinfo/jt/aid/hjs/token` 等附加签名字段 |
| 服务器读回 | 签到 `0→1`，连续天数 `4→5`，积分 `46→52`，成长值 `86848→86862` |

本文件记录的首次成功来自来源项目的入口。迁移后的代码需以自身的只读检查、后续未签到日的首次提交、
实际青龙容器内的结果分别验收；本次迁移不自动创建或启用定时任务，也不代表已完成跨日验证。
奖励随服务器返回变化，不把历史 `+6/+14` 写死为固定奖励。

## 凭证配置

推荐使用与 Cookie 来自同一会话的私有资料 JSON：

- `origin`：固定为 `https://pan.baidu.com`。
- `cookie`：完整登录 Cookie。
- `native_static_params`：上表 8 个静态客户端字段的字符串值；不可加入历史动态签名。
- `user_agent`：与该会话匹配的已验证 User-Agent。

文件格式兼容 one-tap-capture 的 `.local/baidu-auth.json`。资料包含设备标识，按登录凭证管理，
无需在运行期间接入 App、Android SDK、ADB、模拟器、Frida 或 WebView 参数服务。

```bash
# 从已有资料离线导入到本环境的私有持久目录，只允许首次创建
python3 dupan.py --import-auth /private/path/baidu-auth.json
```

也可以设置 `SIGN_AUTH_DUPAN` 指向这个资料文件。文件不写入源码，也不要放在青龙会公开同步的仓库目录。

兼容环境变量方式：

| 变量 | 用途 |
|---|---|
| `SIGN_COOKIE_DUPAN` | 完整 Cookie；显式设置后优先于资料中的 Cookie |
| `SIGN_CLIENT_DUPAN` | 包含 8 个静态字段的 JSON 对象；可覆盖资料中的静态配置 |
| `SIGN_USER_AGENT_DUPAN` | 已验证 User-Agent；可覆盖资料中的值 |
| `SIGN_AUTH_DUPAN` | 可选私有资料文件路径；青龙中必须是容器可访问的路径 |
| `SIGN_STATE_DIR_DUPAN` | 可选私有持久目录 |
| `SIGN_PROXY_DUPAN` / `SIGN_UP_PROXY` | 沿用 k-sign 的显式代理开关和地址 |

完全使用变量时，前 3 项都需要配置。旧 Cookie 配置如果没有客户端资料，会明确失败；
不随机生成设备信息、不自动回退旧签到。任务只支持一个登录资料，多个账号应各自使用独立持久目录。

## 状态持久化

青龙默认使用 `/ql/data/dupan`；本地默认使用本仓库 `data/dupan`（已被 Git 忽略）。
如设置自定义目录，必须放在持久卷中，并避免与其他账号共用。

- `auth.json`：离线导入的初始资料。
- `session.json`：刷新后的 CookieJar，保留 Cookie 域、路径、过期时间等属性。
- `attempt-<账号摘要>.json`：当天提交记录，不包含账号明文。
- `reports/*.json`：仅含接口路径、参数名称、状态、余额差值、业务码和时间的脱敏报告。

运行全过程加互斥锁。文件为 `0600`，专用目录为 `0700`。
用配置来源的 SHA-256 摘要识别用户显式更新；来源未变时优先加载持久 CookieJar，
避免旧环境 Cookie 每次覆盖响应刷新后的 Cookie。更新 Cookie 或资料后，下次运行重新导入新来源。

## 运行与失败行为

1. 加锁、加载凭证，只读验证登录身份。
2. 读取签到首页；若已签到，直接成功跳过，0 次变更。
3. 未签到时读取唯一的 `task_type=166` 及其字符串 ID，然后读回签到列表、日期、连续天数、积分和成长值。
4. 仅在状态一致且当天没有提交记录时，将提交记录落盘，然后发送最多一次签到请求。
5. 成功、业务拒绝或网络超时后均只读回状态与余额；超时不能当作确定失败自动重发。
6. 原子保存 CookieJar 和脱敏报告。重启后仍尊重当天提交记录。

HTTP 层关闭自动重试，禁止重定向，启用 HTTPS 证书校验。
不会隐式继承宿主机 `HTTP_PROXY/HTTPS_PROXY`，需要代理时使用上表明确配置。
跨日、缺失字段、状态矛盾、凭证失效、余额读回失败均返回非零退出码；遇到当天已签到属于正常跳过。

```bash
python3 dupan.py --status       # 只读，0 变更，无通知
python3 dupan.py --no-notify    # 正常签到，关闭本次通知
python3 dupan.py                # 正常签到，使用 k-sign 通知
```

脚本使用 k-sign 已有 Python 依赖和 BaseSign；不新增 Android/浏览器运行依赖。
在青龙完成依赖和凭证配置后，沿用 `task AnTengye_k-sign_master/dupan.py`。
先检查该账号已有定时任务，并在下一未签到日人工验收一次；同一天不要人为删除提交记录后重新尝试。

## 2026-09-08 迁移验收

- 本地 `venv` 中命令行入口验证通过，现有登录资料已离线导入 Git 忽略的 `data/dupan/auth.json`。
- 新入口 `--status` 使用真实 requests 客户端完成登录查询和签到首页查询，均为 HTTP 200、业务码 0。
  状态为今日已签到、连续 5 天、积分 52，本次 2 个只读请求、0 个变更请求。
- 脱敏报告：`data/dupan/reports/20260908-014121-053fae4c.json`。CookieJar 保存成功，文件 `0600`、目录 `0700`。
- 45 项仓库单元测试通过；另外 4 项回环 HTTP 集成测试验证真实请求键名、新随机值、503 不重试、302 不重定向及错误脱敏。
- 尚未推送代码、部署青龙或用迁移后的入口进行新的首次提交；这些验收与来源项目的 S1 成功分开记录。

```bash
python3 -m unittest discover -v
DUPAN_RUN_HTTP_TESTS=1 venv/bin/python -m unittest tests.test_dupan_http -v
```
