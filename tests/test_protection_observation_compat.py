"""Run read-only legacy fixtures with new observer dependencies, isolated outputs."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]

def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    source = (ROOT / 'runtime/rb_learned.c').read_text()
    observer = source[source.index('/* First setup only;'):source.index('/* LS_OBSERVATION_END */')]
    for name, folder in [('test_protection_coverage_audit.py', 'protection-coverage-audit'),
                         ('test_learned_lifecycle_source.py', 'learned-lifecycle-source')]:
        path = ROOT / 'tests' / name
        code = path.read_text().replace(f'artifacts/local/{folder}', f'artifacts/local/protection-observation/compat-{folder}')
        # The legacy source and fixtures remain byte-identical on disk.
        scope = {'__name__': 'protection_observation_compat_' + folder.replace('-', '_'),
                 '__file__': str(path), 'observer': observer}
        exec(compile(code, str(path), 'exec'), scope)
        for value in scope.values():
            if isinstance(value, type) and issubclass(value, unittest.TestCase):
                suite.addTests(loader.loadTestsFromTestCase(value))
    return suite
