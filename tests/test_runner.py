import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import core
import runner

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        for prop, path in {
            'BASE': base, 'CONFIG_FILE': base/'config.json',
            'STATE_FILE': base/'state.json',
            'LOG_FILE': base/'logs'/'sparkkeeper.log',
            'LOCK_FILE': base/'once.lock',
        }.items():
            p = patch.object(core, prop, path)
            p.start(); self.addCleanup(p.stop)
        cfg = core.get_config()
        cfg['contacts'] = [{'name':'好友A', 'enabled':True}]
        core.save_config(cfg)
        self.log = MagicMock()

    def test_skips_friends_already_attempted_today(self):
        core.record('好友A','sent','ok')
        with patch.object(runner, 'sync_playwright') as mock:
            result = runner._execute(self.log, False, '正式发送')
        self.assertEqual(result, 0)
        mock.assert_not_called()

    def test_dry_run_does_not_mark_or_send(self):
        with patch.object(runner, 'sync_playwright') as mock, \
            patch.object(runner, 'browser_context') as ctx, \
            patch.object(runner, 'open_chat'), patch.object(runner, 'open_target'), \
            patch.object(runner, 'send_message') as send:
            ctx.return_value.pages=[MagicMock()]
            result = runner._execute(self.log, True, '仅检查')
        self.assertEqual(result, 0)
        send.assert_not_called()
        self.assertFalse(core.get_state()['results'])

    def test_uncertain_send_blocks_same_day_retry(self):
        def interrupted(page, message, before_send):
            before_send()
            raise runner.UncertainSend('ui not confirmed')
        with patch.object(runner, 'sync_playwright'), \
            patch.object(runner, 'browser_context') as ctx, \
            patch.object(runner, 'open_chat'), patch.object(runner, 'open_target'), \
            patch.object(runner, 'send_message', side_effect=interrupted):
            ctx.return_value.pages=[MagicMock()]
            result = runner._execute(self.log, False, '正式发送')
        self.assertEqual(result, 1)
        self.assertEqual(core.get_state()['results']['好友A']['status'], 'uncertain')

    def test_scheduled_runs_once_and_defaults_to_dry(self):
        with patch.object(runner, 'log_setup', return_value=self.log), patch.object(runner, '_execute', return_value=0) as execute:
            self.assertEqual(runner.run_once(scheduled=True), 0)
            self.assertTrue(execute.call_args.args[1])
            self.assertEqual(runner.run_once(scheduled=True), 0)
            self.assertEqual(execute.call_count, 1)

    def test_scheduled_run_on_next_day_without_restart(self):
        with patch.object(runner, 'log_setup', return_value=self.log), patch.object(runner, '_execute', return_value=0) as execute:
            with patch.object(core, 'today', return_value='2026-11-28'):
                self.assertEqual(runner.run_once(scheduled=True), 0)
                self.assertEqual(runner.run_once(scheduled=True), 0)
                self.assertEqual(execute.call_count, 1)
            with patch.object(core, 'today', return_value='2026-11-29'):
                self.assertEqual(runner.run_once(scheduled=True), 0)
                self.assertEqual(runner.run_once(scheduled=True), 0)
                self.assertEqual(execute.call_count, 2)

    def test_transient_startup_retry_is_bounded_and_cooled_down(self):
        with patch.object(runner, 'log_setup', return_value=self.log), patch.object(runner, '_execute', side_effect=RuntimeError('net::ERR_PROXY_CONNECTION_FAILED')) as execute:
            with patch.object(core.time, 'time', return_value=1000):
                self.assertEqual(runner.run_once(scheduled=True), 1)
                self.assertEqual(runner.run_once(scheduled=True), 0)
                self.assertEqual(execute.call_count, 1)
            for epoch in [2000, 3000, 4000]:
                with patch.object(core.time, 'time', return_value=epoch):
                    runner.run_once(scheduled=True)
            self.assertEqual(execute.call_count, 3)

    def test_single_contact_does_not_send_to_others(self):
        with patch.object(runner, 'sync_playwright'), patch.object(runner, 'browser_context') as ctx, patch.object(runner, 'open_chat'), patch.object(runner, 'open_target') as target, patch.object(runner, 'send_message') as send:
            ctx.return_value.pages = [MagicMock()]
            self.assertEqual(runner._execute(self.log, True, 'test', '好友A'), 0)
            self.assertEqual(target.call_args.args[1], '好友A')
            send.assert_not_called()
        with self.assertRaises(ValueError):
            runner._execute(self.log, True, 'test', 'not configured')

    def test_retryable_contact_retried_but_uncertain_not_retried(self):
        core.record('好友A', 'uncertain')
        with patch.object(runner, 'sync_playwright') as pw:
            self.assertEqual(runner._execute(self.log, False, 'test'), 0)
            pw.assert_not_called()
        core.record('好友A', 'retryable')
        with patch.object(runner, 'sync_playwright'), patch.object(runner, 'browser_context') as ctx, patch.object(runner, 'open_chat'), patch.object(runner, 'open_target'), patch.object(runner, 'send_message') as send:
            ctx.return_value.pages = [MagicMock()]
            runner._execute(self.log, False, 'test')
            send.assert_called_once()

    def test_corrupt_state_fails_closed(self):
        core.STATE_FILE.write_text('{broken', encoding='utf-8')
        with patch.object(runner, 'log_setup', return_value=self.log), patch.object(runner, 'sync_playwright') as browser:
            self.assertEqual(runner.run_once(scheduled=True), 1)
            browser.assert_not_called()

if __name__=='__main__':
    unittest.main()
