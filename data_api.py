"""Public-data adapters. Standard library only; no credentials or trading calls."""
import concurrent.futures as cf
import csv
import datetime as dt
import io
import json
import re
import time
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from poll_sources import DDHQ_API, DDHQ_URL, ddhq_points
from forecast_sources import load_forecast, retain_history

KALSHI = 'https://api.elections.kalshi.com/trade-api/v2'
POLY = 'https://gamma-api.polymarket.com'
SILVER = 'https://static.dwcdn.net/data/rfiFi.csv'
FIFTY = 'https://fiftyplusone.news/polls/generic-ballot/generic-ballot/__data.json'
# All 2026 US Senate seats, including the Florida and Ohio special elections.
STATES = dict(AL='Alabama', AK='Alaska', AR='Arkansas', CO='Colorado', DE='Delaware',
 FL='Florida', GA='Georgia', ID='Idaho', IL='Illinois', IA='Iowa', KS='Kansas',
 KY='Kentucky', LA='Louisiana', ME='Maine', MA='Massachusetts', MI='Michigan',
 MN='Minnesota', MS='Mississippi', MT='Montana', NE='Nebraska', NH='New Hampshire',
 NJ='New Jersey', NM='New Mexico', NC='North Carolina', OH='Ohio', OK='Oklahoma', OR='Oregon',
 RI='Rhode Island', SC='South Carolina', SD='South Dakota', TN='Tennessee', TX='Texas',
 VA='Virginia', WV='West Virginia', WY='Wyoming')

RATE_LOCK = threading.Lock()
LAST_KALSHI = 0

def fetch(url, as_json=True):
    global LAST_KALSHI
    for attempt in range(3):
        try:
            if 'kalshi.com' in url:
                with RATE_LOCK:
                    delay = 0.35 - (time.monotonic() - LAST_KALSHI)
                    if delay > 0: time.sleep(delay)
                    LAST_KALSHI = time.monotonic()
            req = urllib.request.Request(url, headers={'User-Agent': 'ElectionDashboard/1.0', 'Accept': 'application/json,text/csv,*/*'})
            with urllib.request.urlopen(req, timeout=25) as r:
                value = r.read().decode('utf-8-sig')
            return json.loads(value) if as_json else value
        except Exception:
            if attempt == 2: raise
            time.sleep(0.7 * (attempt + 1))

def iso(): return dt.datetime.now(dt.timezone.utc).isoformat()

def unflatten(a):
    cache = {}
    def decode(i):
        if i < 0: return None
        if i in cache: return cache[i]
        v = a[i]
        if isinstance(v, dict):
            cache[i] = z = {}
            z.update({k: decode(n) for k, n in v.items()})
            return z
        if isinstance(v, list):
            cache[i] = z = []
            z.extend(decode(n) for n in v)
            return z
        return v
    return decode(0)

def polling(source, previous=None):
    if source == 'ddhq':
        return {'name': 'DDHQ', 'url': DDHQ_URL, 'api': DDHQ_API,
                'points': ddhq_points(fetch(DDHQ_API)), 'retrieved': iso()}
    if source == 'silver':
        data = []
        for r in csv.DictReader(io.StringIO(fetch(SILVER, False))):
            date = dt.datetime.strptime(r['modeldate'], '%m/%d/%Y').date().isoformat()
            data.append({'date': date, 'd': float(r['dem']), 'r': float(r['rep'])})
        return {'name': 'Silver Bulletin', 'url': 'https://www.natesilver.net/p/generic-ballot-average-2026-nate-silver-bulletin-congress-polls', 'api': SILVER, 'points': data, 'retrieved': iso()}
    raw = fetch(FIFTY)
    node = next(unflatten(n['data']) for n in raw['nodes'] if n and n.get('data') and 'chartData' in n['data'][0])
    data = [{'date': r['end_date'], 'd': r['dem_estimate'], 'r': r['rep_estimate']} for r in node['chartData'] if r.get('subgroup') == 'All polls']
    return {'name': 'FiftyPlusOne', 'url': 'https://fiftyplusone.news/polls/generic-ballot/generic-ballot', 'api': FIFTY, 'points': data, 'retrieved': iso()}

def num(v):
    try:
        x = float(v)
        return x if 0 <= x <= 1 else None
    except (TypeError, ValueError): return None

def kalshi_quote(m):
    bid, ask = num(m.get('yes_bid_dollars')), num(m.get('yes_ask_dollars'))
    if bid is None or ask is None or bid > ask or (bid == 0 and ask == 1):
        return None  # An absent/unusable two-sided quote is not a 50% estimate.
    return {'p': round((bid + ask) * 50, 4), 'bid': bid * 100, 'ask': ask * 100,
            'ticker': m['ticker'], 'event': m['event_ticker'],
            'candidate': m.get('yes_sub_title', ''), 'volume24h': float(m.get('volume_24h_fp', 0)),
            'retrieved': iso(), 'url': 'https://kalshi.com/markets/' + m['event_ticker'].split('-26')[0].lower(), 'history': []}

def get_kalshi():
    tickers = ['SENATE' + s + ('S' if s in ('FL', 'OH') else '') + '-26' for s in STATES]
    out, errors = {}, []
    def load(s):
        j = fetch(KALSHI + '/markets?' + urllib.parse.urlencode({'event_ticker': s, 'status': 'open', 'limit': 1000}))
        if j.get('cursor'): raise ValueError('Unexpected pagination for ' + s)
        return j['markets']
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(load, s): s for s in tickers}
        for f in cf.as_completed(futures):
            try:
                for m in f.result():
                    # Party contracts match across exchanges; exclude primaries and other years.
                    if not re.search(r'-26-R$', m['ticker']): continue
                    state = re.search(r'(?:SENATEPARTY-?|SENATE)([A-Z]{2})(?:S)?-26', m['event_ticker'])
                    if not state or state[1] not in STATES: continue
                    q = kalshi_quote(m)
                    if q and (state[1] not in out or q['volume24h'] > out[state[1]]['volume24h']): out[state[1]] = q
            except Exception as e: errors.append(f"Kalshi {futures[f]}: {e}")
    return out, errors

def race_candidates(markets, state):
    candidates = []
    for market in markets:
        if not market.get('active') or market.get('closed') or not market.get('outcomePrices'):
            continue
        label = market.get('groupItemTitle', '').strip()
        match = re.fullmatch(r'(.+?)\s*\(([DRI])\)', label)
        if match:
            name, party = match.groups()
        elif state == 'AK' and label in ('Mary Peltola', 'Sen. Dan Sullivan'):
            name, party = label.removeprefix('Sen. '), 'D' if label == 'Mary Peltola' else 'R'
        elif state == 'NE' and label == 'Independent':
            # The nonpartisan challenger is listed on Nebraska's official 2026 ballot.
            name, party = 'Dan Osborn', 'I'
        else:
            continue
        if not any(c['name'] == name for c in candidates):
            candidates.append({'name': name, 'party': party})
    return sorted(candidates, key=lambda c: ({'D': 0, 'I': 1, 'R': 2}[c['party']], c['name']))

def get_polymarket():
    events = list(STATES.items())
    out, errors = {}, []
    def load(pair):
        state, name = pair
        slug = name.lower().replace(' ', '-') + '-senate-election-winner'
        if state == 'AL': slug += '-154'
        found = fetch(POLY + '/events?slug=' + slug)
        if not found: return state, None
        e = found[0]
        if e.get('closed') or '2026' not in e.get('description', ''): return state, None
        for m in e['markets']:
            if m.get('closed') or not m.get('active'): continue
            party_contract = bool(re.search(r'\brepublicans?\b', m.get('question', ''), re.I))
            alaska_candidate = state == 'AK' and m.get('groupItemTitle') == 'Mary Peltola'
            if not party_contract and not alaska_candidate: continue
            outcomes = json.loads(m['outcomes']) if isinstance(m['outcomes'], str) else m['outcomes']
            prices = json.loads(m['outcomePrices']) if isinstance(m['outcomePrices'], str) else m['outcomePrices']
            tokens = json.loads(m['clobTokenIds']) if isinstance(m['clobTokenIds'], str) else m['clobTokenIds']
            idx = outcomes.index('Yes')
            p = num(prices[idx])
            if p is None: continue
            return state, {'p': round((1 - p if alaska_candidate else p) * 100, 4), 'contractSide': 'D' if alaska_candidate else 'R', 'yesProbability': round(p * 100, 4), 'bid': num(m.get('bestBid')), 'ask': num(m.get('bestAsk')),
               'candidates': race_candidates(e['markets'], state), 'candidateSpecific': alaska_candidate, 'token': tokens[idx], 'candidate': m.get('groupItemTitle', ''), 'id': m['id'],
               'updated': m.get('updatedAt'), 'retrieved': iso(), 'history': [],
               'url': 'https://polymarket.com/event/' + e['slug']}
        return state, None
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(load, e): e for e in events}
        for f in cf.as_completed(futures):
            try:
                state, q = f.result()
                if q: out[state] = q
            except Exception as e: errors.append(f'Polymarket {futures[f][0]}: {e}')
    return out, errors

def history(source, quote, now):
    start = now - 91 * 86400
    if source == 'kalshi':
        series = quote.get('series') or quote['event'].rsplit('-', 1)[0]
        url = KALSHI + f"/series/{series}/markets/{quote['ticker']}/candlesticks?start_ts={start}&end_ts={now}&period_interval=1440"
        points = []
        for c in fetch(url).get('candlesticks', []):
            bid = num(c.get('yes_bid', {}).get('close_dollars'))
            ask = num(c.get('yes_ask', {}).get('close_dollars'))
            if bid is not None and ask is not None and bid <= ask and (bid, ask) != (0, 1):
                points.append([c['end_period_ts'] * 1000, round((bid + ask) * 50, 4)])
    else:
        url = 'https://clob.polymarket.com/prices-history?' + urllib.parse.urlencode({'market': quote['token'], 'interval': 'max', 'fidelity': 1440})
        points = [[p['t'] * 1000, round((1 - float(p['p']) if quote.get('contractSide') == 'D' else float(p['p'])) * 100, 4)] for p in fetch(url).get('history', []) if start <= p['t'] <= now]
    quote['history'] = sorted(points + [[now * 1000, quote['p']]])
    quote['historyApi'] = url

def senate_control(source, chamber='senate'):
    if chamber not in ('senate', 'house'): raise ValueError('Unknown chamber')
    series = 'CONTROLS' if chamber == 'senate' else 'CONTROLH'
    if source == 'kalshi':
        markets = fetch(KALSHI + f'/markets?event_ticker={series}-2026&status=open&limit=100')['markets']
        m = next(m for m in markets if m['ticker'] == f'{series}-2026-R')
        q = kalshi_quote(m)
        if not q: raise ValueError(f'No usable {chamber} control quote')
        q['series'] = series
    else:
        event = fetch(POLY + f'/events?slug=which-party-will-win-the-{chamber}-in-2026')[0]
        m = next(m for m in event['markets'] if m.get('groupItemTitle') == 'Republican Party' and m.get('active') and not m.get('closed'))
        def array(v): return json.loads(v) if isinstance(v, str) else v
        i = array(m['outcomes']).index('Yes')
        probability = num(array(m['outcomePrices'])[i])
        if probability is None: raise ValueError(f'Invalid {chamber} control quote')
        q = {'p': round(probability * 100, 4), 'contractSide': 'R', 'id': m['id'],
             'token': array(m['clobTokenIds'])[i], 'retrieved': iso(), 'updated': m.get('updatedAt'),
             'url': 'https://polymarket.com/event/' + event['slug'], 'history': []}
    if chamber == 'house': return q
    try:
        history(source, q, int(time.time()))
    except Exception as e:
        q['historyError'] = str(e)
        q['history'] = [[int(time.time()) * 1000, q['p']]]
    return q

def collect(previous=None):
    previous = json.loads(json.dumps(previous or {}))
    # Retired model sources must not return through cached market races.
    for source in set(previous.get('forecasts', {})) - {'fifty'}:
        previous['forecasts'].pop(source)
        for key in ('control', 'house'):
            previous.get(key, {}).pop(source, None)
        for race in previous.get('races', []):
            race.pop(source, None)
    previous['polls'] = dict(previous.get('polls', {}))
    result = {'retrieved': iso(), 'polls': {}, 'races': [], 'errors': [], 'coverage': {}, 'control': {}, 'house': {}, 'forecasts': {}}
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(polling, s, previous.get('polls', {}).get(s)): s for s in ('silver', 'fifty', 'ddhq')}
        k_future = pool.submit(get_kalshi)
        p_future = pool.submit(get_polymarket)
        control_futures = {pool.submit(senate_control, source, chamber): (source, 'control' if chamber == 'senate' else 'house', chamber) for chamber in ('senate', 'house') for source in ('kalshi', 'polymarket')}
        forecast_futures = {pool.submit(load_forecast, source, fetch, iso()): source for source in ('fifty',)}
        for f, source in futures.items():
            try: result['polls'][source] = f.result()
            except Exception as e:
                result['errors'].append(f'{source}: {e}')
                if source in previous.get('polls', {}):
                    result['polls'][source] = dict(previous['polls'][source], stale=True)
        try: k, errors = k_future.result(); result['errors'].extend(errors)
        except Exception as e: k = {}; result['errors'].append(f'Kalshi: {e}')
        try: p, errors = p_future.result(); result['errors'].extend(errors)
        except Exception as e: p = {}; result['errors'].append(f'Polymarket: {e}')
        for future, (source, key, chamber) in control_futures.items():
            try:
                result[key][source] = future.result()
                if result[key][source].get('historyError'):
                    result['errors'].append(source + f' {chamber} control history: ' + result[key][source]['historyError'])
            except Exception as e:
                result['errors'].append(source + f' {chamber} control: ' + str(e))
                if source in previous.get(key, {}):
                    result[key][source] = dict(previous[key][source], stale=True)
        for future, source in forecast_futures.items():
            try:
                result['forecasts'][source] = retain_history(future.result(), previous.get('forecasts', {}).get(source, {}))
            except Exception as e:
                result['errors'].append(source + ' forecast: ' + str(e))
                cached = previous.get('forecasts', {}).get(source)
                if cached:
                    cached = json.loads(json.dumps(cached))
                    for q in [cached['control'], cached['house'], *cached['races'].values()]: q['stale'] = True
                    result['forecasts'][source] = cached
    result['coverage'] = {'kalshi': len(k), 'polymarket': len(p), 'paired': len(k.keys() & p.keys()), 'total': len(STATES), 'missingKalshi': sorted(set(STATES) - set(k)), 'missingPolymarket': sorted(set(STATES) - set(p))}
    # Never mix one fresh platform with an old platform for the ranking.
    if not k or not p:
        result['races'] = previous.get('races', [])
        result['marketsStale'] = True
        result['marketRetrieved'] = previous.get('marketRetrieved', previous.get('retrieved'))
    else:
        for s in k.keys() & p.keys():
            result['races'].append({'state': s, 'name': STATES[s], 'special': s in ('FL','OH'),
                'kalshi': k[s], 'polymarket': p[s], 'candidates': p[s].get('candidates', []),
                'distance': (abs(k[s]['p'] - 50) + abs(p[s]['p'] - 50)) / 2})
        result['races'].sort(key=lambda r: (r['distance'], r['state']))
        result['marketRetrieved'] = iso()
        now = int(time.time())
        with cf.ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(history, source, race[source], now): (race, source)
                for race in result['races'] for source in ('kalshi', 'polymarket')}
            for f in cf.as_completed(futures):
                race, source = futures[f]
                try: f.result()
                except Exception as e:
                    race[source]['historyError'] = str(e)
                    race[source]['history'] = [[now * 1000, race[source]['p']]]
                    result['errors'].append(f"{source} {race['state']} history: {e}")
    catalog_path = Path(__file__).resolve().parent / 'candidate_names.json'
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {}
    for race in result['races']:
        if not race.get('candidates'):
            race['candidates'] = catalog.get(race['state'], [])
    for source, model in result['forecasts'].items():
        result['control'][source] = model['control']
        result['house'][source] = model['house']
        for race in result['races']:
            q = model['races'].get(race['state'])
            if q and ('special' not in q or q['special'] == race['special']): race[source] = q
    return result

if __name__ == '__main__':
    from pathlib import Path
    root = Path(__file__).resolve().parent
    old = json.loads((root / 'snapshot.json').read_text()) if (root / 'snapshot.json').exists() else None
    data = collect(old)
    (root / 'snapshot.json').write_text(json.dumps(data, separators=(',', ':')))
    html = (root / 'dashboard.template.html').read_text()
    (root / 'dashboard.html').write_text(html.replace('__SNAPSHOT__', json.dumps(data, separators=(',', ':')).replace('<', '\\u003c')))
    print(json.dumps({'coverage': data['coverage'], 'errors': data['errors'], 'top10': [(r['state'], r['kalshi']['p'], r['polymarket']['p']) for r in data['races'][:10]]}, indent=2))
