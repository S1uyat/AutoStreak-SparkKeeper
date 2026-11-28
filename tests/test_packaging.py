import sys
import tempfile
from pathlib import Path
from contextlib import ExitStack
import unittest
from unittest.mock import patch
import app
import app_runtime

class PackagingTests(unittest.TestCase):
    def test_theme_toggle_persists_without_changing_contacts(self):
        import core
        from manager import Manager
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            base = Path(tmp)
            for key, path in {'BASE': base, 'CONFIG_FILE': base/'config.json', 'STATE_FILE': base/'state.json', 'LOG_FILE': base/'logs'/'test.log', 'LOCK_FILE': base/'once.lock'}.items():
                stack.enter_context(patch.object(core, key, path))
            stack.enter_context(patch.object(Manager, 'probe_schedule'))
            cfg = core.get_config()
            cfg['contacts'] = [{'name': 'Demo', 'enabled': False}]
            core.save_config(cfg)
            window = Manager()
            window.withdraw()
            try:
                window.toggle_theme()
                self.assertEqual(core.get_config()['theme'], 'dark')
                window.toggle_theme()
                self.assertEqual(core.get_config()['theme'], 'light')
                self.assertEqual(core.get_config()['contacts'], cfg['contacts'])
                self.assertFalse(core.get_config()['auto_send'])
            finally:
                window.destroy()

    def test_single_contact_cli_routes_target(self):
        with patch('runner.run_once', return_value=0) as run:
            app.main(['--run', '--dry-run', '--target', 'Demo'])
            run.assert_called_once_with(dry_run=True, scheduled=False, target='Demo')

    def test_frozen_runner_uses_exe_not_extracted_script(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', r'C:\Programs\SparkKeeper.exe'):
            self.assertEqual(app_runtime.runner_command(True), [r'C:\Programs\SparkKeeper.exe', '--run', '--dry-run'])
            args = app_runtime.task_command('install')
            self.assertEqual(args[-2:], ['-ExecutablePath', r'C:\Programs\SparkKeeper.exe'])

    def test_entry_dry_run_routes_without_gui(self):
        with patch('runner.run_once', return_value=0) as run:
            self.assertEqual(app.main(['--run','--dry-run']), 0)
            run.assert_called_once_with(dry_run=True, scheduled=False)

    def test_entry_schedule_uses_daily_guard(self):
        with patch('runner.run_once', return_value=0) as run:
            app.main(['--run','--scheduled'])
            run.assert_called_once_with(dry_run=False, scheduled=True)

if __name__ == '__main__':
    unittest.main()
