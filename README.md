# k-sign 青龙部署

## 启动青龙

项目镜像基于青龙 `2.20.2-debian`，并在构建时安装签到脚本所需的 Python 依赖：

```bash
docker compose build
docker compose up -d
```

默认监听 `0.0.0.0:5700`。可以通过 `QL_BIND_ADDRESS` 和 `QL_PORT` 调整，例如仅允许本机访问：

```bash
QL_BIND_ADDRESS=127.0.0.1 docker compose up -d
```

## 拉取签到脚本

```bash
ql repo "https://github.com/AnTengye/k-sign.git" "" "onnx|json|base|notify|gifcode|tools|expired|slidecode|test|dupan_signing" "onnx|json|base.py|notify.py|gifcode.py|tools.py|slidecode.py|dupan_signing.py" "" "py|onnx|json" ""
```

## 每日签到汇总通知

各个签到任务执行完毕后默认不再单独推送通知，而是将当日执行结果写入 `/ql/data/ksign_summary/YYYY-MM-DD.json`（本地回退 `data/ksign_summary/`），由 `daily_summary.py`（默认每天 `20:30`）统一汇总推送一条通知：

```text
【今日成功X条，失败X条，失败任务：xx、xx】
```

如需恢复每个任务单独推送通知，可在青龙环境变量中设置 `SIGN_NOTIFY_EACH=1`。

## 本地测试

```bash
python3 -m unittest discover -v
```

## New API 站点签到

`newapi.py` 支持多个站点，可在青龙环境变量中为每个站点使用相同后缀配置。
例如南梁 API（`api.llm.pm`）使用个人访问令牌签到：

```text
SIGN_URL_NEWAPI_LLMPM=https://api.llm.pm
SIGN_TOKENS_NEWAPI_LLMPM=5073|<个人访问令牌>
```

账号 ID 使用 `/api/user/self` 返回的 `id`。令牌配置每行一个 `user_id|token`，
无需同时设置该站点的 `SIGN_UP_NEWAPI_LLMPM`；其他站点仍可使用原有的账号密码配置。
只在青龙环境变量中保存真实令牌，不要写入仓库。

已有的 `newapi.py` 定时任务会自动发现这些站点，无需为每个站点新建任务。
脚本先读取今日签到状态，已签到时直接跳过。

## 百度网盘任务中心签到

`dupan.py` 已切换为 App「成长值任务 / 去签到」对应的 `/coins/taskcenter/signin`。
只执行签到。每日答题、任务上报和答题领奖已停用，人工 `--claim-probe` 入口已撤下；无需额外添加参数。

当前使用 2026-09-08 成功验证的 S1 集合：完整 Cookie、8 个已验证静态客户端字段和
User-Agent，以及本地新生成的 `rand/time`。支持导入私有登录资料，或使用
`SIGN_COOKIE_DUPAN`、`SIGN_CLIENT_DUPAN`、`SIGN_USER_AGENT_DUPAN` 三个变量。
仅沿用旧 Cookie 变量不够，缺少静态字段时会停止。

```bash
# 离线导入登录资料（不会覆盖已有文件，不请求百度）
python3 dupan.py --import-auth /private/path/baidu-auth.json

# 登录及签到状态只读检查，不提交也不推送通知
python3 dupan.py --status

# 正常签到，使用现有 k-sign 通知设置
python3 dupan.py
```

完整配置、持久目录和验证范围见 [百度网盘签到说明](docs/dupan.md)。
