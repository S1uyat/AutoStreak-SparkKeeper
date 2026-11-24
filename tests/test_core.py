import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import core

class StoreTests(unittest.TestCase):
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
            p.start()
            self.addCleanup(p.stop)

    def test_config_persists(self):
        cfg = core.get_config()
        cfg['contacts'] = [{'name':'朋友甲','enabled':True}]
        core.save_config(cfg)
        self.assertEqual(core.get_config()['contacts'][0]['name'], '朋友甲')

    def test_duplicate_name_rejected(self):
        cfg = core.get_config()
        cfg['contacts'] = [{'name':'A'},{'name':'A'}]
        with self.assertRaises(ValueError):
            core.save_config(cfg)

    def test_daily_state_marks_and_reads(self):
        core.record('A', 'sent', 'message bubble')
        self.assertEqual(core.get_state()['results']['A']['status'], 'sent')
        self.assertEqual(core.get_state()['date'], core.today())

    def test_next_day_resets(self):
        core.write_json(core.STATE_FILE, {'date':'2020-01-01','results':{'A':{'status':'sent'}}})
        self.assertEqual(core.get_state()['results'], {})

    def test_lock_excludes_parallel_runs(self):
        with core.ExecutionLock():
            with self.assertRaises(core.AlreadyRunning):
                with core.ExecutionLock():
                    pass
        with core.ExecutionLock():
            pass

if __name__=='__main__':
    unittest.main()
