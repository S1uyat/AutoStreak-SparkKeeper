"""One-shot process invoked by Windows Task Scheduler. No service, tray, or event loop."""
from __future__ import annotations
import argparse
import logging
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from core import (AlreadyRunning, ExecutionLock, get_config, get_state, log_setup,
                  record, validate_config, nowstr, claim_scheduled_run, set_retry_pending)
from browser import (browser_context, open_chat, open_target, send_message,
                     NeedLogin, VerificationRequired, TargetNotFound, UncertainSend)


def run_once(dry_run=False, scheduled=False, target=None):
    logger = log_setup()
    kind = '仅检查，不发送' if dry_run else '正式发送'
    try:
        with ExecutionLock():
            if scheduled:
                if not claim_scheduled_run():
                    logger.info('今天的自动任务已经执行，退出。')
                    return 0
                dry_run = dry_run or not get_config().get('auto_send', False)
                kind = '仅检查，不发送' if dry_run else '正式发送'
            try:
                result = _execute(logger, dry_run, kind, target) if target else _execute(logger, dry_run, kind)
                if scheduled and not dry_run:
                    set_retry_pending(any(v.get('status') == 'retryable' for v in get_state()['results'].values()))
                return result
            except Exception as exc:
                if scheduled:
                    set_retry_pending(is_transient(exc), str(exc))
                raise
    except AlreadyRunning as e:
        logger.warning(str(e))
        return 2
    except Exception:
        logger.exception('任务出现未处理的异常')
        return 1


def is_transient(exc):
    return isinstance(exc, PWTimeout) or any(code in str(exc) for code in (
        'ERR_PROXY_CONNECTION_FAILED', 'ERR_INTERNET_DISCONNECTED', 'ERR_NETWORK_CHANGED',
        'ERR_CONNECTION_RESET', 'ERR_CONNECTION_TIMED_OUT', 'ERR_NAME_NOT_RESOLVED'))


def _execute(logger, dry_run, kind, target=None):
    started_at = time.monotonic()
    config = get_config()
    validate_config(config)
    contacts = [c['name'] for c in config['contacts'] if c.get('enabled', True)]
    if target is not None:
        if target not in contacts:
            raise ValueError('所选好友不存在或已暂停，请先启用。')
        contacts = [target]
    # Uniqueness enforced by config validator; no automatic retries for attempted names.
    attempted = {} if dry_run else get_state()['results']
    due = [name for name in contacts if dry_run or name not in attempted or attempted[name].get('status') == 'retryable']
    logger.info('任务开始 [%s]；已启用 %s 人；待检查/发送 %s 人', kind, len(contacts), len(due))
    if not due and not dry_run:
        logger.info('没有待执行的好友（当日可能已经尝试过），退出。')
        return 0

    failures = 0
    with sync_playwright() as playwright:
        ctx = None
        try:
            phase_started = time.monotonic()
            ctx = browser_context(playwright, config['channel'], headless=bool(config['headless']))
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            open_chat(page)
            startup_seconds = time.monotonic() - phase_started
            target_seconds = send_seconds = 0.0
            for name in due:
                started = [False]
                try:
                    phase_started = time.monotonic()
                    open_target(page, name)
                    target_seconds += time.monotonic() - phase_started
                    if dry_run:
                        logger.info('检查通过：%s（未发送消息）', name)
                        continue

                    def mark_pending():
                        record(name, 'uncertain', '已准备点击发送；若进程中断，今天不再自动重发。')
                        started[0] = True

                    phase_started = time.monotonic()
                    send_message(page, config['message'], mark_pending)
                    send_seconds += time.monotonic() - phase_started
                    record(name, 'sent', '检测到新的己方消息气泡；平台是否计入火花需自行确认。')
                    logger.info('发送已在界面确认：%s', name)
                except (NeedLogin, VerificationRequired) as exc:
                    failures += 1
                    logger.error('停止：%s', exc)
                    if not dry_run and started[0]:
                        record(name, 'uncertain', str(exc))
                    break
                except UncertainSend as exc:
                    failures += 1
                    if not dry_run:
                        record(name, 'uncertain', str(exc))
                    logger.warning('发送状态不确定：%s — %s', name, exc)
                except Exception as exc:
                    failures += 1
                    status = 'uncertain' if started[0] else ('retryable' if is_transient(exc) else 'failed')
                    if not dry_run:
                        record(name, status, str(exc))
                    logger.error('%s：%s — %s', '发送结果不明' if started[0] else '执行失败', name, exc)
            logger.info('阶段耗时：浏览器和页面 %.2f 秒；好友定位 %.2f 秒；发送确认 %.2f 秒', startup_seconds, target_seconds, send_seconds)
            logger.info('任务结束 [%s]；本轮异常 %s 个；耗时 %.2f 秒', kind, failures, time.monotonic() - started_at)
            return 0 if failures == 0 else 1
        except (NeedLogin, VerificationRequired) as exc:
            logger.error('无法启动任务：%s', exc)
            return 1
        finally:
            if ctx:
                ctx.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SparkKeeper Windows one-shot runner')
    parser.add_argument('--dry-run', action='store_true', help='仅检查好友，绝不发送')
    parser.add_argument('--scheduled', action='store_true', help='每日首次登录任务')
    parser.add_argument('--target', help='仅处理这个已启用好友')
    args = parser.parse_args()
    sys.exit(run_once(dry_run=args.dry_run, scheduled=args.scheduled, target=args.target))
