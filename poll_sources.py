"""Parsers for the publishers' public generic-ballot chart data."""
import datetime as dt
from html.parser import HTMLParser
import re
from zoneinfo import ZoneInfo

DDHQ_URL = 'https://embeds-2026.ddhq.io/polls/generic-ballot/national/lv-rv-adults/'
DDHQ_API = DDHQ_URL + '_payload.json'
RCP_URL = 'https://www.realclearpolling.com/polls/state-of-the-union/generic-congressional-vote'


def decode_nuxt(values):
    cache = {}
    def decode(index):
        if index < 0:
            return None
        if index in cache:
            return cache[index]
        value = values[index]
        if isinstance(value, list) and value and isinstance(value[0], str) and value[0] in {'Reactive', 'ShallowReactive', 'Ref', 'ShallowRef'}:
            return decode(value[1])
        if isinstance(value, dict):
            cache[index] = result = {}
            result.update({k: decode(v) for k, v in value.items()})
            return result
        if isinstance(value, list):
            cache[index] = result = []
            result.extend(decode(v) for v in value)
            return result
        return value
    return decode(0)


def ddhq_points(payload):
    decoded = decode_nuxt(payload)
    average = next(v['pollAverage'] for v in decoded['data'].values()
                   if isinstance(v, dict) and isinstance(v.get('pollAverage'), dict)
                   and v['pollAverage'].get('slug') == '/generic-ballot/national/lv-rv-adults')
    candidates = {}
    for options in average['option_candidate_map'].values():
        for candidate_id, candidate in options.items():
            name = candidate.get('label', candidate.get('poll_ag_name', '')).lower()
            if name in {'democrat', 'democratic', 'republican'}:
                candidates[int(candidate_id)] = 'r' if name == 'republican' else 'd'
    points = {}
    for sample in average['timeseries']:
        row = {'date': sample['date'][:10]}
        dt.date.fromisoformat(row['date'])
        for result in sample['data']:
            if result['cand_id'] in candidates:
                row[candidates[result['cand_id']]] = float(result['value'])
        if {'d', 'r'} <= row.keys() and all(0 <= row[k] <= 100 for k in ('d', 'r')):
            points[row['date']] = row
    if not points:
        raise ValueError('DDHQ chart contains no valid party-average observations')
    return [points[k] for k in sorted(points)]


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        if tag in ('td', 'th') and self.row is not None: self.cell = []
    def handle_data(self, value):
        if self.cell is not None: self.cell.append(value)
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def rcp_observation(html, observed_at):
    parser = Tables()
    parser.feed(html)
    democratic, republican = None, None
    for row in parser.rows:
        d = next((i for i, s in enumerate(row) if s.lower().startswith('democrats')), None)
        r = next((i for i, s in enumerate(row) if s.lower().startswith('republicans')), None)
        if d is not None and r is not None:
            democratic, republican = d, r
        if row and row[0].strip().lower() == 'rcp average':
            if democratic is None or republican is None:
                raise ValueError('RCP table party ordering is missing; refusing to guess')
            def percentage(text):
                if not re.fullmatch(r'\d+(?:\.\d+)?\s*%?', text):
                    raise ValueError('Invalid RCP average')
                value = float(text.replace('%', '').strip())
                if not 0 <= value <= 100: raise ValueError('Invalid RCP percentage')
                return value
            date = dt.datetime.fromisoformat(observed_at).astimezone(ZoneInfo('America/Los_Angeles')).date().isoformat()
            return {'date': date, 'd': percentage(row[democratic]), 'r': percentage(row[republican])}
    raise ValueError('RCP average unavailable in the public response; retaining the last verified observation')
