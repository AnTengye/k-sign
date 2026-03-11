# k-sign 项目指南

## 项目概述

这是一个基于 Python 的多站点自动签到/签到脚本集合，设计用于在**青龙面板 (QingLong Panel)** 上定时执行。项目通过继承 `BaseSign` 基类，为各个论坛/网站实现自动登录、签到、回帖等操作，并通过多渠道消息推送通知执行结果。

## 技术栈

- **语言**: Python 3.8+
- **HTTP 请求**: `requests`，`curl_cffi`
- **HTML 解析**: `scrapy.Selector` (Xpath / 正则)
- **验证码识别**: `ddddocr`，`opencv-python-headless`，`Pillow`
- **ONNX 模型**: `djgame_cd.onnx` (点选验证码识别)
- **运行环境**: 青龙面板 Docker 容器
- **部署**: `Dockerfile` + `docker-compose.yml`

## 架构设计

### 核心模块

| 文件 | 职责 |
|---|---|
| `base.py` | 基类 `BaseSign`，封装通用登录（普通/验证码/Cookie）、签到（GET/POST）、日志、重试、代理等逻辑 |
| `notify.py` | 多渠道消息推送（Bark/钉钉/飞书/企业微信/Telegram/ServerJ/PushDeer/PushPlus 等） |
| `gifcode.py` | GIF/图片验证码识别 |
| `slidecode.py` | 滑块验证码处理 |
| `tools.py` | 工具函数 |

### 站点签到脚本

每个 `.py` 文件（除核心模块外）对应一个站点的签到实现，继承 `BaseSign` 并重写或扩展：

- `login()` — 站点特定的登录逻辑
- `sign()` — 站点特定的签到逻辑
- 其他自定义方法（如 `auto_reply()`）通过 `exec_method` 列表注册

活跃脚本在根目录，已失效的在 `expired/` 目录。

### 执行流程

```
run() → _exec()
  ├─ pre()           # 前置操作（可选）
  ├─ login()         # 登录
  ├─ exec_method[]   # 遍历执行注册的方法（如 sign, auto_reply）
  └─ notify.send()   # 推送结果通知
```

## 环境变量规范

脚本通过环境变量配置，命名规范为 `SIGN_XXX_{app_key}`：

- `SIGN_URL_{app_key}` — 站点地址
- `SIGN_UP_{app_key}` — 账号密码，格式：`用户名|密码`
- `SIGN_COOKIE_{app_key}` — Cookie 登录方式用
- `SIGN_PROXY_{app_key}` — 代理开关
- `SIGN_UP_PROXY` — 全局代理地址

消息推送相关变量见 `notify.py` 中的 `push_config` 字典。

## 开发规范

### 新增站点签到

1. 创建 `{site_name}.py`，类继承 `BaseSign`
2. 在 `__init__` 中调用 `super().__init__(base_url, app_name, app_key)`
3. 设置 `self.exec_method` 注册需要执行的方法
4. 实现 `login()` 和 `sign()` 等方法
5. 文件顶部添加青龙面板的 cron 注释：
   ```python
   """
   cron: 0 15 18 * * *
   new Env('站点名称签到');
   """
   ```
6. 文件末尾添加入口：
   ```python
   if __name__ == "__main__":
       s = YourSign()
       s.run()
   ```

### 代码风格

- 使用 `self.pwl()` 记录日志，不要直接 `print`
- 使用 `self.session` 发起请求（已配置超时、重试、代理）
- 使用 `scrapy.Selector` 解析 HTML 响应
- 登录失败时 `login()` 返回 `False`，成功返回 `True`
- 验证码识别优先使用 `gifcode.py` 中的 `handle_yzm`

### 注意事项

- 不要修改 `base.py`、`notify.py`、`gifcode.py` 等核心模块，除非有明确需求
- `expired/` 目录存放已失效脚本，仅作参考
- `djgame_cd.onnx` 和 `djgame_char.json` 是 `djgame.py` 专用的验证码模型文件
- 青龙面板拉库命令会自动排除 `onnx|json|base|notify|gifcode` 等核心文件
