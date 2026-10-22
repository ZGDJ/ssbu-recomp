import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('writer', Path(__file__).resolve().parents[1] / 'tools/analyze_writer_probe.py')
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)

BEGIN = 'WRITER_BEGIN v=1 frame=119 installed=3 skipped=0 failed=0 status=armed offsets=529b844,529b848,6dd52e8,593b470 width=4 scope=existing_threads observer=debug_registers authoritative=0'
EVENT = 'WRITER_EVENT v=1 index=0 phase=replay thread=42 mask=2 post_rip=1010 module_base=1000 module_offset=10 guest_candidate=710398b8a0'
END = 'WRITER_END v=1 frame=120 from=119 recorded=1 pending=0 inflight=0 dropped=0 arming=0 replay=1 cleaned=3 cleanup_failed=0 status=collected'


class WriterProbeTests(unittest.TestCase):
    def test_research_only(self):
        result = writer.analyze([BEGIN, EVENT, END])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['status'], 'research_only')

    def test_missing_duplicate_and_order(self):
        for rows in ([], [BEGIN, END], [BEGIN, EVENT], [BEGIN, EVENT, EVENT, END], [EVENT, BEGIN, END]):
            with self.subTest(rows=rows):
                self.assertTrue(writer.analyze(rows)['errors'])

    def test_failures_and_coverage(self):
        for old, new in [('collected', 'truncated'), ('inflight=0', 'inflight=1'), ('pending=0', 'pending=1'),
                         ('dropped=0', 'dropped=1'), ('cleanup_failed=0', 'cleanup_failed=1'), ('frame=120', 'frame=121')]:
            with self.subTest(new=new):
                self.assertTrue(writer.analyze([BEGIN, EVENT, END.replace(old, new)])['errors'])

    def test_malformed_attribution(self):
        for old, new in [('mask=2', 'mask=10'), ('module_offset=10', 'module_offset=11'), ('phase=replay', 'phase=unknown'),
                         ('index=0', 'index=1'), ('v=1', 'v=2'), ('guest_candidate=710398b8a0', 'guest_candidate=-1'),
                         ('guest_candidate=710398b8a0', 'guest_candidate=10000000000000000')]:
            with self.subTest(new=new):
                self.assertTrue(writer.analyze([BEGIN, EVENT.replace(old, new), END])['errors'])

    def test_scope_and_metadata(self):
        for old, new in [('authoritative=0', 'authoritative=1'), ('width=4', 'width=8'), ('skipped=0', 'skipped=1'), ('status=armed', 'status=partial')]:
            with self.subTest(new=new):
                self.assertTrue(writer.analyze([BEGIN.replace(old, new), EVENT, END])['errors'])
        self.assertTrue(writer.analyze([BEGIN + ' width=4', EVENT, END])['errors'])

    def test_full_buffer_is_not_complete(self):
        events = [EVENT.replace('index=0', f'index={i}') for i in range(128)]
        end = END.replace('recorded=1 ', 'recorded=128 ').replace('replay=1 ', 'replay=128 ')
        self.assertTrue(writer.analyze([BEGIN, *events, end])['errors'])
