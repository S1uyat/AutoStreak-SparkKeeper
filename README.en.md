# SparkKeeper


[简体中文](README.md) | **English**

![Vibe Coded](https://img.shields.io/badge/Vibe_Coded-AI_assisted-8A2BE2)
![Built with OpenAI Codex](https://img.shields.io/badge/Built_with-OpenAI_Codex-412991)

A Windows desktop tool for maintaining friend streaks on **Douyin (抖音, the Chinese version of TikTok)**. Sign in by scanning a QR code, choose your contacts, and schedule a daily message run at Windows sign-in and every day at midnight. The process exits when finished; no resident background service is installed.

> **Vibe coding disclosure:** SparkKeeper is developed iteratively with substantial AI assistance from OpenAI Codex. The maintainer directs requirements and performs local testing. This describes the development process, not a certification of correctness or security.

## New in v0.2.0

- Two-page desktop UI with persistent light/dark themes. Light: white, `#0533B0`, `#C8C8C8`. Dark: `#000002`, `#221F23`, `#0450D3`.
- Daily summary and per-contact explanations, single-contact dry run and sending.
- Local audit of the latest 200 contact changes, with undo for the latest enable/pause change. Earlier changes cannot be reconstructed.
- Bounded recovery for transient failures before sending. Uncertain sends are never automatically repeated.
- Confirmation requires a new matching message bubble and a cleared editor, with a failure check. This is not a recipient delivery receipt.

## Features

- Desktop management panel and manual QR-code sign-in.
- Contact management, configurable message text, and a dry run that sends nothing.
- Daily per-contact deduplication, including attempts with an uncertain outcome.
- Local run logs and Windows Task Scheduler setup.
- A standalone Windows EXE with Python and Playwright included.

This is an English guide; the application interface is currently in Chinese.

## Download and setup

Download `SparkKeeper.exe` from [GitHub Releases](https://github.com/S1uyat/AutoStreak-SparkKeeper/releases/latest), save it to a permanent folder such as `D:\Apps\SparkKeeper`, and launch `SparkKeeper.exe`.

Requirements: Windows 10/11 x64, Microsoft Edge, and an internet connection. You do not need to install Python. Browser binaries are not bundled: the default `msedge` channel uses your installed Edge; `chrome` requires Chrome, and `chromium` requires a separately installed matching Playwright browser.

A fresh installation has no contacts or account credentials, and automatic real sending is disabled.

1. Click **扫码登录 / 重新验证** (QR sign-in / reverify). Scan the code on the official page and complete any verification yourself.
2. Add the exact contact nickname or remark, or load your direct-message conversations and enable selected contacts. Give contacts with duplicate names unique remarks.
3. Save your message and run **测试（不发送）** (test without sending).
4. After checking the intended recipients, enable **允许每日自动任务真实发送** (allow the daily task to send real messages) and save.
5. Click **安装开机自启** (install the Windows sign-in task). You may then close the management panel.

The task triggers at Windows sign-in without an added delay and daily at 00:00 local time. If the PC stays on and you remain signed in, the next day runs without a restart. Daily deduplication prevents repeated sends; eligible pre-send failures may be retried. The task does not wake a sleeping PC; missed runs can start when available. If signed out, sign in again. After upgrading, reinstall the task from the management panel to apply the new triggers. Its browser is hidden; check the logs for progress. Task Scheduler briefly checks every 15 minutes. Eligible transient pre-send failures can retry after at least 15 minutes, with at most three scheduled attempts per day (initial plus two retries). After completion, checks exit without opening a browser. Confirmed sends, uncertain outcomes and other failures are not automatically repeated. Login and verification require manual intervention.

Keep the EXE in its installed location. If you move it, reinstall the scheduled task. You can remove the task from the management panel. Avoid moving the EXE or opening the login browser while a task is running.

## Local data and privacy

Settings, browser sessions, send records, and logs are stored in `%LOCALAPPDATA%\SparkKeeper`, outside the EXE. Do not share this directory. Release packages contain no user account data.

The EXE and source version share the current Windows user's data by default. Upgrading preserves sign-in and deduplication records. Set `SPARK_KEEPER_HOME` to a separate directory for isolated diagnostics.

## Command line

```powershell
.\SparkKeeper.exe                         # Open the management panel
.\SparkKeeper.exe --run --dry-run         # Check contacts without sending
.\SparkKeeper.exe --run --scheduled       # Daily run; respects automatic-send setting
.\SparkKeeper.exe --run                   # Real sending; respects daily contact deduplication
```

Single-contact check: `SparkKeeper.exe --run --dry-run --target "Exact contact name"`. Removing `--dry-run` enables real sending.

The windowed EXE does not print results to the terminal. Read the run logs in the management panel.

## Run from source and build

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm SparkKeeper.spec
```

Locally verified with Python 3.14, Playwright 1.65.2, and PyInstaller 6.22.3. The output is `dist\SparkKeeper.exe`. You can also use `build.ps1`. Build the Windows executable on Windows.

Offline self-test:

```powershell
Start-Process .\dist\SparkKeeper.exe -ArgumentList '--self-test', 'C:\Temp\sparkkeeper-check.json' -Wait
```

Create the report's parent directory first. The self-test uses temporary isolated data to check the Tk interface, Edge launch, safe default settings, and scheduled-task command generation. It does not visit Douyin, send messages, or register a task.

## Limitations and licensing

- Page changes, expired sessions, network failures, or platform verification may interrupt a run. SparkKeeper cannot guarantee that Douyin credits a streak.
- Contact matching uses exact nicknames or remarks.
- The project does not bypass verification or use private messaging APIs.
- The initial release is unsigned. Windows may show an unknown-publisher warning; use the published SHA256 checksums to verify download integrity.
- Use only your own account and consenting contacts, and follow the platform's rules.
- Third-party licenses are listed in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) and [third_party_licenses/](third_party_licenses/). No open-source license has been selected for this project's original code; public source visibility does not grant an open-source redistribution license.

## Automated builds

The repository includes a manually triggered Windows build workflow. It produces downloadable build artifacts; it does not send Douyin messages or automatically publish a GitHub release.
