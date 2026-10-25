"""FiftyPlusOne state-level Senate general-election polling averages."""
import datetime as dt
from poll_sources import decode_nuxt

BASE = 'https://fiftyplusone.news/'
INDEX = BASE + 'polls/senate/general/texas/__data.json'
SLUGS = {'alabama': 'AL', 'alaska': 'AK', 'arkansas': 'AR', 'colorado': 'CO', 'delaware': 'DE', 'florida': 'FL',
         'georgia': 'GA', 'idaho': 'ID', 'illinois': 'IL', 'iowa': 'IA', 'kansas': 'KS', 'kentucky': 'KY',
         'louisiana': 'LA', 'maine': 'ME', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
         'mississippi': 'MS', 'montana': 'MT', 'nebraska': 'NE', 'new-hampshire': 'NH', 'new-jersey': 'NJ',
         'new-mexico': 'NM', 'north-carolina': 'NC', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR',
         'rhode-island': 'RI', 'south-carolina': 'SC', 'south-dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX',
         'virginia': 'VA', 'west-virginia': 'WV', 'wyoming': 'WY'}


def nodes(payload):
    return [decode_nuxt(n['data']) for n in payload['nodes'] if n and n.get('data')]


def senate_slugs(payload):
    """State slugs that FiftyPlusOne publishes a Senate general-election average for."""
    for node in nodes(payload):
        races = (node.get('averagesText') or {}).get('generalAverages', {}).get('races')
        if races:
            return [r['link'].rsplit('/', 1)[-1] for r in races if r.get('link', '').startswith('polls/senate/general/')]
    raise ValueError('No Senate average index')


def parse_average(payload, slug, retrieved, days=120):
    """Latest and recent-history D-R margin; the non-Republican leader stands for D (NE: independent)."""
    node = next((n for n in nodes(payload) if n.get('chartData')), None)
    if node is None:
        raise ValueError('No chart data')
    rows = [r for r in node['chartData'] if r.get('polltype') == 'general' and isinstance(r.get('estimate'), (int, float))]
    by_date = {}
    for r in rows:
        by_date.setdefault(r['end_date'], {}).setdefault('r' if r['party'] == 'REP' else 'd', []).append(r)
    series = []
    for date in sorted(by_date):
        side = by_date[date]
        if 'r' in side and 'd' in side:
            r, d = max(side['r'], key=lambda x: x['estimate']), max(side['d'], key=lambda x: x['estimate'])
            series.append((date, d, r))
    if not series:
        raise ValueError('No paired average')
    date, d, r = series[-1]
    cutoff = (dt.date.fromisoformat(date) - dt.timedelta(days=days)).isoformat()
    return {'date': date, 'd': d['estimate'], 'r': r['estimate'], 'dName': d['candidate_name'], 'dParty': d['party'],
            'rName': r['candidate_name'], 'margin': round(d['estimate'] - r['estimate'], 2),
            'url': BASE + 'polls/senate/general/' + slug, 'retrieved': retrieved,
            'history': [[int(dt.datetime.fromisoformat(x + 'T12:00:00+00:00').timestamp() * 1000), round(dd['estimate'] - rr['estimate'], 2)]
                        for x, dd, rr in series if x >= cutoff]}


def load_state_polls(fetch, retrieved):
    result = {}
    slugs = [s for s in senate_slugs(fetch(INDEX)) if s in SLUGS]
    errors = []
    for slug in slugs:
        try:
            result[SLUGS[slug]] = parse_average(fetch(f'{BASE}polls/senate/general/{slug}/__data.json'), slug, retrieved)
        except Exception as e:
            errors.append(f'{slug}: {e}')
    if not result:
        raise ValueError('No state averages loaded' + (': ' + errors[0] if errors else ''))
    return result, errors
