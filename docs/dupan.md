# 百度网盘 App 任务中心签到

`dupan.py` 对应 App「我的 → 用户名旁 VIP → 成长值任务 / 去签到 → 任务中心」。
2026-10-30 根据用户反馈，答题任务领奖提示“账号或设备异常”，命令行入口已改为只执行
`/coins/taskcenter/signin`。每日答题、任务上报、答题领奖和人工 `--claim-probe` 入口均已停用，
`--status` 也只检查登录与签到状态。旧 `/rest/2.0/membership/level?method=signin` 仍已移除。
现有登录资料和签到防重记录继续使用；历史答题、领奖资料与记录保留，但正常签到不读取它们。

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

首次签到的原始验收来自来源项目的入口；迁移后的签到与青龙情况见文末。
脚本本身不直接管理定时任务，青龙订阅按脚本头信息添加任务。
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
- `question-<账号摘要>.json`：历史答题、上报和领奖记录，现已停用，不参与签到。
- `reports/*.json`：仅含接口路径、参数名称、状态、余额差值、业务码、奖励响应的安全摘要和时间的脱敏报告。
- `claim-signing.json`、`sofire-material.json`：历史领奖私有材料，现已停用，签到不读取。

运行全过程加互斥锁。文件为 `0600`，专用目录为 `0700`。
用配置来源的 SHA-256 摘要识别用户显式更新；来源未变时优先加载持久 CookieJar，
避免旧环境 Cookie 每次覆盖响应刷新后的 Cookie。更新 Cookie 或资料后，下次运行重新导入新来源。

## 运行与失败行为

1. 加锁、加载凭证，只读验证登录身份。
2. 读取签到首页；若已签到，直接成功跳过，0 次变更。
3. 未签到时读取唯一的 `task_type=166` 及其字符串 ID，然后读回签到列表、日期、连续天数、积分和成长值。
4. 仅在状态一致且当天没有提交记录时，将提交记录落盘，然后发送最多一次签到请求。
5. 成功、业务拒绝或网络超时后均只读回状态与余额；超时不能当作确定失败自动重发。
6. 原子保存 CookieJar 和脱敏报告。重启后仍尊重当天签到的提交记录。

HTTP 层关闭自动重试，禁止重定向，启用 HTTPS 证书校验。
不会隐式继承宿主机 `HTTP_PROXY/HTTPS_PROXY`，需要代理时使用上表明确配置。
跨日、缺失字段、状态矛盾、凭证失效、余额读回失败均返回非零退出码；遇到当天已签到属于正常跳过。

```bash
python3 dupan.py --status       # 只读签到状态，0 变更，无通知
python3 dupan.py --no-notify    # 仅签到，关闭本次通知
python3 dupan.py                # 同上，使用 k-sign 通知
python3 dupan.py --sign-only    # 兼容旧命令，与默认行为相同
```

签到使用 k-sign 已有 Python 依赖和 BaseSign，无需 Node、`jsdom`、HTJ SDK、
App、ADB、模拟器或签名服务。
在青龙完成依赖和凭证配置后，沿用 `task AnTengye_k-sign_master/dupan.py`。
先检查该账号已有定时任务，并在下一未签到日人工验收一次；同一天不要人为删除提交记录后重新尝试。

## 历史答题与领奖实验（2026-10-30 起停用）

以下记录保留旧实验的结果与失败边界，不代表当前命令行行为。旧 `--claim-probe` 命令已撤下。

### 2026-09-24 纯脚本答题验收与领奖边界

- 本地现有账号当天已由青龙完成签到。新入口从持久的私有资料读取会话，未启动 App、ADB、模拟器、浏览器或签名服务。
- 当天唯一题目先读为 `answer_status=-1`，唯一 `task_type=169` 任务状态为 `0`。
- 脚本各发送一次提交答案和完成上报，HTTP 都为 `200`、业务码都为 `0`；服务端读回分别为题目 `-1→1`、任务 `0→6`。
- 答案请求只有已有静态客户端字段、当前题目 ID/答案和新 `rand/time`；上报另带当前任务 ID、UK 和本地 MD5 `token`。两次均没有 `z/jt`。
- 任务状态 `6` 仍待领奖，积分和成长值没有新增；本次整体退出码为 `1`，不可宣称答题奖励已到账。
- [当前官方任务脚本](https://staticplat.cdn.bcebos.com/taskSystem/js/index.2cf72c2e.js) 对 `/api/taskscore/antisave` 仍使用 HTJ SDK 参数。已有的基础参数及普通浏览器 HTJ 组合返回业务码 `8001`；成功的历史领奖请求使用了 App 原生桥接及 HTJ 参数。尚无独立生成领奖所需参数并成功领取的证据，因此不发送该请求。

### 2026-09-24 一次性无 App 领奖实验准备

现已从已登录的本机模拟器**一次性**提取同账号的网络签名材料，保存在 Git 忽略的私有目录，未放入源码或青龙订阅仓库。对已保存的成功领奖请求进行离线校验：`dupan_signing.py` 仅用 `BDUSS`、原生账号 UID、加密 SK、时间、设备 ID、版本和已验证 APK 的签名证书摘要，就能逐值重现其 `rand/rand2`；`rchannel` 也按客户端公式逐值匹配。此校验不等于服务端接受缺少其他字段的领奖请求。

青龙映射私有目录中的 `/ql/data/dupan/claim-signing.json` 为 `0600`，只含 `uid`、`encrypted_sk`、`account_uk_sha256`。它不属于 `SIGN_AUTH_DUPAN`、订阅仓库或青龙环境变量；不要复制进 Git。此阶段保留默认 `08:20` 定时任务行为不变：签到、答题、上报后状态 `6` 仍明确报待领取，**当时不会自动领奖**。

新命令 `python3 dupan.py --claim-probe` 最初是人工触发的一次性实验，不在脚本头部声明独立定时任务，也不会先签到或重复答题。只有读回当天题目正确、任务状态 `6`、已签到、账号与私有签名资料一致且当天未试过时，才发送最多一次领奖请求。请求前先落盘当天提交记录；拒绝、超时或读回不一致均不自动重试。2026-09-26 起它与每日入口共享防重判定，领奖成功但响应不含奖励数值时会明确标记为仅经服务端状态和余额读回确认。

2026-09-24 当天已经使用 App 参数领取，无法再验证首次领奖。2026-09-25 已按上述条件执行了唯一一次无 App 实验：青龙 08:20 完成签到、答题和上报，领奖前题目状态 `1`、任务状态 `6`；08:42 的 `/api/taskscore/antisave` 返回 HTTP `200`、业务码 `8001`。脚本只发送这一次领奖请求，读回仍为任务状态 `6`，积分与成长值均 `+0`，当天 `claim_probe` 记录保留，不重试、不用 App 补领。脱敏证据位于私有持久目录 `reports/20260925-004201-cd0a4176.json`。

当前官方脚本将 `8001` 标为 `HTJError`。成功的历史请求另有 `z/jt/hjs` 等参数，但这个业务码不能单独证明哪个字段必需。离线研究从已验证 APK 的 Sofire `Asc.itb` 还原 `z` 的字段布局，`dupan_signing.py` 的生成器对 12 份私有历史样本均逐字复现。稳定设备材料已存入 Git 忽略的私有 `sofire-material.json`，并在运行时核对账号与设备摘要。

2026-09-25 下午定位到本机代理规则将两个反爬域名直连，导致 TLS 握手失败。在 Clash Verge 当前订阅的自定义规则中，仅为 `sofire.bdstatic.com` 与 `sfp.safe.baidu.com` 增加 `AK` 出口并重新激活；经代理两域名均可访问，青龙容器可通过 `host.docker.internal:7890` 使用该出口。官方 SDK v3.5.11 在青龙的 Node 22 + `jsdom` 30 中用当前私有设备资料独立生成了非空 `jt`（只核对长度，不输出 token），未启动 App、模拟器、ADB 或浏览器。再次逐键比对历史成功请求后，人工领奖路径改用实际的 `task_ids/task_froms`，并合入新鲜 `z/jt/aid/ev/hjs/c/ver/ua`、客户端包 `offlinepackage/themeinfo` 与已有签名字段；客户端包信息只在私有文件中。**这只证明本地参数生成与传输链路，尚未证明服务端接受领奖**。9 月 25 日已有一次失败的领奖提交记录，不清除、不重试；须在下一个符合条件且无 `claim_probe` 记录的日期，人工只执行一次并读回状态和奖励，再决定是否接入每日任务。

### 2026-09-26 纯脚本领奖验收与每日接入

青龙 08:20 完成当天签到、答题和上报后，人工只执行一次 `--claim-probe`：事前题目状态 `1`、任务状态 `6`，当天没有领奖记录，官方 SDK 通过容器代理生成非空 `jt`。纯脚本 `/api/taskscore/antisave` 返回 HTTP `200`、业务码 `0`；服务端任务读回 `6→1`，积分 `+6`、成长值 `+3`。本轮没有启动 App、模拟器、ADB 参数服务或浏览器，也没有第二次领奖提交。私有脱敏报告为 `reports/20260926-004240-c3f1dfbb.json`。

该版实验脚本只保存了业务码和状态/余额增量，没有保存领奖响应的安全摘要；因而**本次不能逐字段核对响应中的奖励数值**。历史同任务的 App 参数成功响应曾记录 `addScore=6`、`addGrowScore=3`，与本次到账一致，但不能代替本次响应。实验版因此退出码为 `1`、状态 `claim_needs_review`，不是请求被拒绝或奖励未到账。接入每日流程后，脚本在服务端状态 `1` 与正向余额增量均确认时成功；如本次响应包含可解析的奖励数值，仍强制核对一致性，否则报告 `claimed_readback_only` 和脱敏响应结构。该接受标准只基于服务端读回，不能被表述为响应数值已核对。

## 2026-09-08 迁移验收

- 本地 `venv` 中命令行入口验证通过，现有登录资料已离线导入 Git 忽略的 `data/dupan/auth.json`。
- 功能提交 `dd96fc8` 已推送到 `origin/master`；本地 Docker 青龙订阅 ID 3 拉取成功，容器仓库 HEAD 与远端一致，
  `dupan.py` 的 SHA-256 与工作区文件一致。
- 青龙自动新增并启用任务 ID 337：`task AnTengye_k-sign_master/dupan.py`，计划为每天 `08:20`。
- 青龙启用了 `SIGN_AUTH_DUPAN=/ql/data/dupan/auth.json`；私有资料字段完整，文件 `0600`、目录 `0700`。
- 容器内新入口 `--status` 使用真实 requests 客户端完成登录查询和签到首页查询，均为 HTTP 200、业务码 0。
  状态为今日已签到、连续 5 天、积分 52，本次 2 个只读请求、0 个变更请求；脱敏报告为
  `data/dupan/reports/20260908-031547-4e92787f.json`。
- 45 项常规仓库测试通过；另外 4 项回环 HTTP 集成测试验证真实请求键名、新随机值、503 不重试、
  302 不重定向及错误脱敏。
- 仍待下一未签到日用迁移后的青龙入口验收一次真实首次提交；它与来源项目已经完成的 S1 首次成功分开记录。

```bash
python3 -m unittest discover -v
DUPAN_RUN_HTTP_TESTS=1 venv/bin/python -m unittest tests.test_dupan_http -v
```
