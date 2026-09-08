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
ql repo "https://github.com/AnTengye/k-sign.git" "" "onnx|json|base|notify|gifcode|tools|expired|slidecode|test" "onnx|json|base.py|notify.py|gifcode.py|tools.py|slidecode.py" "" "py|onnx|json" ""
```

## 本地测试

```bash
python3 -m unittest discover -v
```

## 百度网盘任务中心签到

`dupan.py` 已切换为 App「成长值任务 / 去签到」对应的 `/coins/taskcenter/signin`。
只执行签到，旧会员签到、每日答题和领奖已移出该入口。

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
