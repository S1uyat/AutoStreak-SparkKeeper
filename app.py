"""SparkKeeper executable entry point. No arguments opens the manager."""
import argparse
import json
import multiprocessing
import sys
from pathlib import Path

VERSION = '0.1.1'


def self_test(report_path):
    """Offline packaging check; never loads account data or sends messages."""
    import os
    import tempfile
    import subprocess
    with tempfile.TemporaryDirectory(prefix='SparkKeeper-check-') as temp:
        os.environ['SPARK_KEEPER_HOME'] = temp
        from app_runtime import task_command
        from manager import Manager
        from core import get_config
        from playwright.sync_api import sync_playwright
        app = Manager()
        try:
            app.update()
            assert not app.auto_send.get()
            assert not get_config()['contacts']
        finally:
            app.destroy()
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page()
                page.set_content('<title>SparkKeeper offline test</title>')
                assert page.title() == 'SparkKeeper offline test'
            finally:
                browser.close()
        proc = subprocess.run(task_command('plan'), capture_output=True, text=True,
                              encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW,
                              timeout=30, check=True)
        plan = json.loads(proc.stdout)
        result = {'version': VERSION, 'gui': 'ok', 'browser': 'ok',
                  'default_auto_send': False, 'contacts': 0, 'task_plan': plan}
        Path(report_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='SparkKeeper')
    parser.add_argument('--run', action='store_true', help='Run once and exit')
    parser.add_argument('--scheduled', action='store_true', help='Daily first-logon mode')
    parser.add_argument('--dry-run', action='store_true', help='Never send messages')
    parser.add_argument('--self-test', metavar='REPORT_JSON', help='Offline packaging test')
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test(args.self_test)
    if args.run or args.scheduled or args.dry_run:
        from runner import run_once
        return run_once(dry_run=args.dry_run, scheduled=args.scheduled)
    from manager import Manager
    Manager().mainloop()
    return 0


if __name__ == '__main__':
    multiprocessing.freeze_support()
    try:
        sys.exit(main())
    except Exception:
        from core import log_setup
        log_setup().exception('SparkKeeper 启动或运行失败')
        if len(sys.argv) == 1:
            from tkinter import messagebox
            messagebox.showerror('SparkKeeper', '启动失败，请查看本地 SparkKeeper 日志。')
        sys.exit(1)
