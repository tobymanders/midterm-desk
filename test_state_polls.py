import unittest
from state_polls import parse_average, senate_slugs


def nuxt(obj):
    """Encode a plain object as a minimal Nuxt devalue payload."""
    values = []
    def add(v):
        if isinstance(v, dict):
            i = len(values); values.append(None); values[i] = {k: add(x) for k, x in v.items()}; return i
        if isinstance(v, list):
            i = len(values); values.append(None); values[i] = [add(x) for x in v]; return i
        values.append(v); return len(values) - 1
    add(obj)
    return {'nodes': [{'type': 'data', 'data': values}]}


def row(date, name, party, est):
    return {'end_date': date, 'candidate_name': name, 'party': party, 'estimate': est, 'polltype': 'general'}


class StatePollTests(unittest.TestCase):
    def test_margin_uses_latest_paired_day(self):
        rows = [row('2026-10-24', 'D One', 'DEM', 48.0), row('2026-10-24', 'R One', 'REP', 47.0),
                row('2026-10-25', 'D One', 'DEM', 49.1), row('2026-10-25', 'R One', 'REP', 45.6)]
        q = parse_average(nuxt({'chartData': rows}), 'texas', 'now')
        self.assertEqual((q['d'], q['r'], q['margin'], q['date']), (49.1, 45.6, 3.5, '2026-10-25'))
        self.assertEqual(len(q['history']), 2)

    def test_independent_stands_for_the_democratic_side(self):
        rows = [row('2026-10-25', 'Dan Osborn', 'IND', 46.0), row('2026-10-25', 'Pete Ricketts', 'REP', 48.0)]
        q = parse_average(nuxt({'chartData': rows}), 'nebraska', 'now')
        self.assertEqual((q['dName'], q['margin']), ('Dan Osborn', -2.0))

    def test_index_lists_senate_links_only(self):
        races = [{'link': 'polls/senate/general/ohio'}, {'link': 'polls/governor/general/ohio'}]
        self.assertEqual(senate_slugs(nuxt({'averagesText': {'generalAverages': {'races': races}}})), ['ohio'])


if __name__ == '__main__':
    unittest.main()
