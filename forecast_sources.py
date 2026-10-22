"""Public model forecasts, kept distinct from market-implied probabilities."""
import datetime as dt
import json
import math
import re
from poll_sources import decode_nuxt

FIFTY = 'https://fiftyplusone.news/forecast/'
PF = 'https://www.pollingforecast.com'


def probability(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Invalid model probability')
    return value * 100


def quote(d, r, url, api, retrieved, model_date=None, independent=0):
    d, r, independent = probability(d), probability(r), probability(independent)
    if abs(d + r + independent - 100) > .15:
        raise ValueError('Model outcome probabilities do not sum to 100')
    timestamp = int(dt.datetime.fromisoformat(model_date + 'T12:00:00+00:00' if model_date else retrieved).timestamp() * 1000)
    return {'p': round(r, 4), 'd': round(d, 4), 'i': round(independent, 4),
            'nonbinary': independent > .15 and d > .15, 'kind': 'model',
            'modelDate': model_date, 'retrieved': retrieved, 'url': url, 'api': api,
            'history': [[timestamp, round(r, 4)]]}


def fifty_forecast(payload, chamber, retrieved):
    decoded = [decode_nuxt(n['data']) for n in payload['nodes'] if n and n.get('data')]
    data = next(n for n in decoded if 'summary' in n)
    summary = data['summary']
    rows = [r for r in summary if r.get('state_abb') is None and r.get('party') == 'DEM'
            and r.get('variable') == 'seats' and r.get('metric') == 'p_win' and r.get('chamber') == chamber]
    row = max(rows, key=lambda r: r['model_date'])
    api, url = FIFTY + chamber + '/__data.json', FIFTY + chamber
    control = quote(row['value'], 1-row['value'], url, api, retrieved, row['model_date'])
    races = {}
    if chamber == 'senate':
        for state, race in data['seatWinProbs'].items():
            # The Republican probability is explicit; do not mislabel independents as Democrats.
            if state == 'NE':
                d, independent = 0, 1-race['rep_chance']
            else:
                d, independent = race['dem_chance'], race['ind_chance']
            races[state] = quote(d, race['rep_chance'], url, api, retrieved, row['model_date'], independent)
    return control, races


def pf_races(payload, retrieved):
    if payload.get('dataset') != 'senate': raise ValueError('Not a Senate forecast dataset')
    races = {}
    for row in payload['rows']:
        if row.get('kind') != 'Senate' or row.get('left_party') not in ('D', 'I'): continue
        state = row['state']
        # Keep each state's regular/special contract identifiable when joining sources.
        if state in races: raise ValueError('Multiple Senate contests for one state require explicit matching')
        left = row['chance_left']
        races[state] = quote(left if row['left_party'] == 'D' else 0, 1-left,
            PF + row['page'], PF + '/api/us/senate', retrieved, payload['asOf'],
            left if row['left_party'] == 'I' else 0)
        races[state]['special'] = bool(row['special'])
    if not races: raise ValueError('No usable Senate model probabilities')
    return races


def pf_control(html, retrieved):
    match = re.search(r'<script\b(?=[^>]*\bid=["\']wd-us["\'])[^>]*>(.*?)</script>', html, re.S)
    if not match: raise ValueError('Polling Forecast control data unavailable')
    data = json.loads(match[1])['us']
    # senR is explicit: the residual is an independent holding the balance, not a Republican win.
    d, r = data['senD'], data['senR']
    control = quote(d, r, PF + '/us/senate', PF + '/us', retrieved, independent=max(0, 1-d-r))
    house = quote(data['house'], 1-data['house'], PF + '/us', PF + '/us', retrieved)
    return control, house


def load_forecast(source, fetch, retrieved):
    if source == 'fifty':
        control, races = fifty_forecast(fetch(FIFTY + 'senate/__data.json'), 'senate', retrieved)
        house, _ = fifty_forecast(fetch(FIFTY + 'house/__data.json'), 'house', retrieved)
    elif source == 'pollingforecast':
        races = pf_races(fetch(PF + '/api/us/senate'), retrieved)
        control, house = pf_control(fetch(PF + '/us', False), retrieved)
    else: raise ValueError('Unknown forecast source')
    return {'control': control, 'house': house, 'races': races}


def retain_history(current, previous):
    """Keep published/observed points only; repeated model dates replace that date's reading."""
    for group in ('control', 'house'):
        merge_history(current[group], previous.get(group, {}))
    for state, q in current['races'].items():
        merge_history(q, previous.get('races', {}).get(state, {}))
    return current


def merge_history(current, previous):
    points = {p[0]: p[1] for p in previous.get('history', [])}
    points.update(dict(current['history']))
    current['history'] = sorted([[t, p] for t, p in points.items()])[-730:]
