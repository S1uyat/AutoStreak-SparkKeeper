import sys
import unittest
from unittest.mock import patch
import app
import app_runtime

class PackagingTests(unittest.TestCase):
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
