"""Build the self-contained public site; optionally refresh its public API data."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from data_api import collect

ROOT = Path(__file__).resolve().parent


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, encoding='utf-8', delete=False) as f:
        temporary = Path(f.name)
        f.write(text)
    try:
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build(output, refresh=False):
    saved = output / 'snapshot.json'
    if not saved.exists():
        saved = ROOT / 'snapshot.json'
    previous = json.loads(saved.read_text()) if saved.exists() else None
    data = collect(previous) if refresh else previous
    if not data or not data.get('polls') or not data.get('races') or not data.get('control'):
        raise ValueError('Incomplete dashboard data; refusing to publish an empty site')
    if refresh and all(p.get('stale') for p in data['polls'].values()) and data.get('marketsStale'):
        raise ValueError('All sources failed; keeping the previously published site')
    payload = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c')
    template = (ROOT / 'dashboard.template.html').read_text()
    if 'const STATIC_HOSTING = false;' not in template:
        raise ValueError('Static hosting flag is missing from the template')
    html = template.replace('const STATIC_HOSTING = false;', 'const STATIC_HOSTING = true;').replace('__SNAPSHOT__', payload)
    atomic_write(output / 'snapshot.json', payload)
    atomic_write(output / 'index.html', html)
    atomic_write(output / '.nojekyll', '')
    # Keep a local fallback for collectors and cache it between scheduled builds.
    if refresh:
        atomic_write(ROOT / 'snapshot.json', payload)
    print(json.dumps({'published_to': str(output), 'retrieved': data['retrieved'], 'errors': data.get('errors', [])}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'public')
    args = parser.parse_args()
    build(args.output.resolve(), args.refresh)
