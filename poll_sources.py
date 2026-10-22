"""Parsers for the publishers' public generic-ballot chart data."""
import datetime as dt

DDHQ_URL = 'https://embeds-2026.ddhq.io/polls/generic-ballot/national/lv-rv-adults/'
DDHQ_API = DDHQ_URL + '_payload.json'


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
