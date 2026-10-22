import unittest
from forecast_sources import fifty_forecast, pf_races, pf_control, merge_history, quote

NOW = '2026-10-22T05:43:00+00:00'


def payload(value):
    flat = []
    def encode(v):
        i = len(flat)
        flat.append(None)
        flat[i] = ({k: encode(x) for k, x in v.items()} if isinstance(v, dict)
                   else [encode(x) for x in v] if isinstance(v, list) else v)
        return i
    encode(value)
    return {'nodes': [{'data': flat}]}


class ForecastTest(unittest.TestCase):
    def test_fifty_extracts_win_probability_not_expected_seats(self):
        control, races = fifty_forecast(payload({
            'summary': [
                {'state_abb': None, 'party': 'DEM', 'variable': 'seats', 'metric': 'median', 'chamber': 'senate', 'value': 52, 'model_date': '2026-10-21'},
                {'state_abb': None, 'party': 'DEM', 'variable': 'seats', 'metric': 'p_win', 'chamber': 'senate', 'value': .7509, 'model_date': '2026-10-21'}],
            'seatWinProbs': {'NE': {'rep_chance': .7856, 'dem_chance': .2144, 'ind_chance': 0},
                             'AK': {'rep_chance': .3316, 'dem_chance': .6684, 'ind_chance': 0}}}), 'senate', NOW)
        self.assertEqual(control['p'], 24.91)
        self.assertEqual(races['AK']['p'], 33.16)
        self.assertEqual(races['NE']['i'], 21.44)
        self.assertEqual(races['NE']['d'], 0)

    def test_pollingforecast_preserves_independent_balance(self):
        control, house = pf_control('<script type="application/json" id="wd-us">{"us":{"senD":0.454,"senR":0.487,"house":0.702}}</script>', NOW)
        self.assertEqual((control['d'], control['p'], control['i']), (45.4, 48.7, 5.9))
        self.assertTrue(control['nonbinary'])
        self.assertEqual(house['p'], 29.8)

    def test_specials_and_independents_match_without_party_guessing(self):
        races = pf_races({'dataset': 'senate', 'asOf': '2026-10-20', 'rows': [
            {'kind': 'Senate', 'state': 'OH', 'special': True, 'left_party': 'D', 'chance_left': .55, 'page': '/us/senate/oh-s'},
            {'kind': 'Senate', 'state': 'NE', 'special': False, 'left_party': 'I', 'chance_left': .274, 'page': '/us/senate/ne'}]}, NOW)
        self.assertTrue(races['OH']['special'])
        self.assertEqual(races['NE']['i'], 27.4)
        self.assertFalse(races['NE']['nonbinary'])
        self.assertEqual(races['OH']['history'][0][0], 1792497600000)

    def test_history_is_not_backfilled_and_same_model_date_replaces(self):
        previous = quote(.6, .4, '', '', NOW, '2026-10-20')
        current = quote(.65, .35, '', '', NOW, '2026-10-21')
        merge_history(current, previous)
        revised = quote(.66, .34, '', '', NOW, '2026-10-21')
        merge_history(revised, current)
        self.assertEqual([p[1] for p in revised['history']], [40, 34])

    def test_invalid_probabilities_are_not_silently_clamped(self):
        for d, r in [(75, 25), (.8, .8), (float('nan'), .5), (True, 0)]:
            with self.subTest(d=d), self.assertRaises(ValueError): quote(d, r, '', '', NOW)
        with self.assertRaises(ValueError): pf_control('<html>Unavailable</html>', NOW)


if __name__ == '__main__':
    unittest.main()
