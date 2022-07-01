# 自定义python版本青龙docker部署
## 注意事项
- libgl1-mesa-glx 为部分库依赖
- 清华源：`pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`
- 注意将github.com替换为：hub.fastgit.xyz
- local问题：
  - apt-get install -y locales locales-all
  - locale-gen en_US.UTF-8