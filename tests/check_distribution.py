"""Run after uv build. Install wheel and sdist offline into isolated temporary venvs."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import tempfile
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    wheels = list((ROOT / 'dist').glob('*.whl'))
    sources = list((ROOT / 'dist').glob('*.tar.gz'))
    assert len(wheels) == len(sources) == 1, 'Expected one current wheel and sdist'
    with zipfile.ZipFile(wheels[0]) as z:
        names = z.namelist()
        assert any(n == 'agent_evaluation_core/__init__.py' for n in names)
        assert all(n.startswith(('agent_evaluation_core/', 'agent_evaluation_core-')) for n in names)
    with tarfile.open(sources[0]) as tar:
        names = tar.getnames()
        assert not any(part in ('.venv', '__pycache__', '.pytest_cache', 'dist', '.env')
                       for name in names for part in Path(name).parts)
        assert any(name.endswith('/PROVENANCE.md') for name in names)
        assert any(name.endswith('/RUBRIC.md') for name in names)
    for artifact in [wheels[0], sources[0]]:
        with tempfile.TemporaryDirectory(prefix='evaluation-install-') as tmp:
            tmp = Path(tmp)
            env = tmp / 'venv'
            run('uv', 'venv', str(env), cwd=tmp)
            python = str(env / 'bin/python')
            run('uv', 'pip', 'install', '--offline', '--python', python, str(artifact), cwd=tmp)
            smoke = '''
import importlib.util, json, pathlib, sys
from agent_evaluation_core import ResponseEvaluator, EvaluationError, evaluation_schema
assert importlib.util.find_spec('pandas') is None
for absent in ['response_eval', 'database', 'llm', 'observability', 'chat_clients', 'adversarial_prompt_gen']:
    assert importlib.util.find_spec(absent) is None, absent
assert 'site-packages' in __import__('agent_evaluation_core').__file__
class Client:
    def chat(self, **kwargs): raise AssertionError('No judge needed for empty response')
r = ResponseEvaluator(Client(), system_prompt='Fixture').evaluate_pair('p','')
assert r['kind'] == 'system_error' and r['aggregate_score'] == 0
print('isolated core import/rules: OK')
'''
            run(python, '-I', '-c', smoke, cwd=tmp)
            output = subprocess.check_output([python, '-I', str(ROOT / 'demo.py')], cwd=tmp, text=True)
            cases = json.loads(output)
            assert [c['synthetic_judge_calls'] for c in cases] == [0, 0, 0, 1]
            assert [c['result']['aggregate_score'] for c in cases] == [0.0, 0.1, None, 0.9]
            print(f'{artifact.name}: installed and offline demo verified')


def full_suite():
    """Check the locked optional adapter and tests against the installed wheel."""
    wheel = next((ROOT / 'dist').glob('*.whl'))
    for version in ('3.11', '3.12', '3.13'):
        with tempfile.TemporaryDirectory(prefix='evaluation-full-' + version + '-') as tmp:
            tmp = Path(tmp)
            checkout = tmp / 'project'
            shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns(
                '.venv', '__pycache__', '.pytest_cache', 'dist'))
            run('uv', 'sync', '--offline', '--frozen', '--extra', 'dataframe',
                '--python', version, cwd=checkout)
            python = str(checkout / '.venv/bin/python')
            run('uv', 'pip', 'install', '--offline', '--python', python,
                '--reinstall', '--no-deps', str(wheel), cwd=tmp)
            run(python, '-I', '-c',
                "import agent_evaluation_core as c; assert 'site-packages' in c.__file__", cwd=tmp)
            run(python, '-I', '-m', 'pytest', str(checkout / 'tests'),
                '-q', '-p', 'no:cacheprovider', cwd=tmp)
            output = subprocess.check_output([python, '-I', str(checkout / 'demo.py')], cwd=tmp, text=True)
            assert [case['result']['aggregate_score'] for case in json.loads(output)] == [0, .1, None, .9]
            print('Installed wheel tests and offline demo on Python ' + version + ': OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Also run locked full suite on installed Python 3.11/3.12/3.13; requires cached optional/dev wheels')
    args = parser.parse_args()
    main()
    if args.full:
        full_suite()
