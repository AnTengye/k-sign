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
