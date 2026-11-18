# Python 包安装的证书安全边界

Python 的 [emSign CA 安全公告](https://discuss.python.org/t/109576)要求更新 pip、其内置证书和独立 certifi。
项目使用 pip 26.2.2、certifi 2026.10.19；独立 certifi 由生产依赖和锁文件精确固定。
更新独立 certifi 不会修复 pip 内置副本，也不会修复操作系统信任库。

首次普通联网安装前，在后端目录运行：

```sh
sh bootstrap_pip.sh .venv/bin/python
```

脚本仅从公告给出的官方 URL 下载 pip wheel，固定 SHA256 校验后离线安装；不查询其他索引，
不关闭 TLS、不添加 trusted-host。完成后只读检查 OpenSSL 默认根集合；若仍信任被移除的
emSign ECC Root CA - G3，会停止后续安装。应通过官方系统/基础镜像的正常证书包更新修复，
不能靠手改信任列表绕过。本检查只覆盖 OpenSSL 可见的这一受影响根，不代替完整平台信任链审计。

CI 和 Docker 先正常更新 ca-certificates，再复用该脚本。pre-commit CI 将已校验 wheel 保存在
runner 临时目录，virtualenv 固定从该目录离线播种 pip 26.2.2，并禁用 seed 周期下载；
缓存键包含引导脚本，避免复用旧 pip 环境。全局 uv 和其他项目环境需要分别升级核验。

安装后可离线检查实际版本：

```sh
.venv/bin/python -m pip --version
.venv/bin/python -c 'import certifi, pip._vendor.certifi as vendor; print(certifi.__version__, vendor.__version__)'
```

本地测试通过或制品哈希一致，只能证明相应功能/文件一致，不能追溯证明过去的下载链路安全。
