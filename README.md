# SparkKeeper


**简体中文** | [English](README.en.md)

![Vibe Coded](https://img.shields.io/badge/Vibe_Coded-AI_assisted-8A2BE2)
![Built with OpenAI Codex](https://img.shields.io/badge/Built_with-OpenAI_Codex-412991)

> **Vibe Coding 开发说明：** 本项目在 OpenAI Codex 的大量 AI 辅助下迭代开发，由维护者提出需求并进行本机测试。该标注说明开发方式，不代表正确性或安全认证。

Windows 抖音好友火花维护工具：扫码登录、好友管理、每日去重、运行日志，以及登录 Windows 时和每天零点触发的任务计划。任务执行完成后退出，不安装后台服务。

## 下载与使用

从 [GitHub Releases](https://github.com/S1uyat/AutoStreak-SparkKeeper/releases/latest) 下载 `SparkKeeper.exe`，保存到固定目录（例如 `D:\Apps\SparkKeeper`），双击 `SparkKeeper.exe`。

- 支持 Windows 10/11 x64，需要已安装 Microsoft Edge 和网络连接。
- EXE 已包含 Python 与 Playwright，无需另装 Python。
- 不附带抖音账号或登录信息。首次启动时好友为空，自动真实发送默认关闭。
- 默认使用 `msedge`；`chrome` 需要自行安装 Chrome，`chromium` 需要另外安装匹配版本的 Playwright 浏览器。EXE 不包含这些浏览器。

首次设置：

1. 点击“扫码登录 / 重新验证”，在官方页面手动扫码；验证由本人完成。
2. 添加好友的准确备注或昵称，或读取私信会话后启用指定好友。
3. 保存发送内容，运行“测试（不发送）”。
4. 确认目标无误后，勾选“允许每日自动任务真实发送”并保存。
5. 点击“安装开机自启”，完成后可关闭管理面板。

Windows 登录时立即触发，同时每天本机时间 00:00 触发；保持开机且用户仍登录时，无需重启即可执行新一天的任务。每日去重确保同一天只执行一次。睡眠期间不主动唤醒，错过定时后由任务计划在可用时补跑；注销时需下次登录。升级后请再次点击“安装开机自启”以更新触发器。运行期间不显示浏览器窗口，因此请通过日志查看进度。首次任务失败也不会在当天自动重试；可以查看日志、修复原因后手动执行。每个已经尝试的好友（含结果不确定）当天不会再次发送。

EXE 放置位置必须保持固定。移动文件后请重新安装开机任务。取消自启可在管理面板操作。不要在任务运行期间移动 EXE 或同时打开登录浏览器。

## 本地数据与隐私

配置、浏览器登录会话、发送记录和日志保存在 `%LOCALAPPDATA%\SparkKeeper`，不写入 EXE。不要分享该目录。发布包不包含任何使用者账号资料。

EXE 与源码版默认共用当前 Windows 用户的数据，升级不会清除登录或去重记录。诊断测试可设置 `SPARK_KEEPER_HOME` 指向独立目录。

## 命令行

```powershell
.\SparkKeeper.exe                         # 管理界面
.\SparkKeeper.exe --run --dry-run         # 只检查，绝不发送
.\SparkKeeper.exe --run --scheduled       # 每日首次执行，遵守自动发送开关
.\SparkKeeper.exe --run                   # 真实发送，遵守好友当日去重
```

窗口版 EXE 不向终端输出结果，请查看管理面板中的运行日志。

## 源码运行与构建

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm SparkKeeper.spec
```

本机验证环境：Python 3.14、Playwright 1.65.2、PyInstaller 6.22.3。打包结果为 `dist\SparkKeeper.exe`。也可以运行 `build.ps1`。必须在 Windows 上构建 Windows EXE。

离线自检（不会进入抖音、不会发送消息、不会注册任务）：

```powershell
Start-Process .\dist\SparkKeeper.exe -ArgumentList '--self-test', 'C:\Temp\sparkkeeper-check.json' -Wait
```

报告父目录需已存在。自检使用临时独立数据，检查 Tk 界面、Edge 启动、默认关闭真实发送，以及任务计划命令生成。

## 限制与授权

- 页面更新、登录失效、网络问题或平台验证可能导致失败，软件不能保证平台计入火花。
- 当前通过准确昵称/备注确认好友，同名联系人请先设置唯一备注。
- 项目不提供绕过验证的能力，不使用私有发信接口。
- 首个发布包未做代码签名，Windows 可能显示“未知发布者”；可用发布的 SHA256 文件核对下载完整性。
- 仅用于本人账号和得到同意的联系人，遵守平台使用规则。
- 第三方组件许可见 `THIRD_PARTY_NOTICES.txt` 与 `third_party_licenses/`。本项目原始代码尚未选定开源许可；公开展示源码不等于授予开源再分发许可。

## 自动构建

仓库提供 Windows 构建工作流，可手动触发。构建产物用于下载与检查，不会自动发送抖音消息或自动发布 GitHub Release。
