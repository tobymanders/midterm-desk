import unittest
from poll_sources import ddhq_points, rcp_observation


class PollSourcesTest(unittest.TestCase):
    def test_ddhq_maps_parties_by_candidate_id(self):
        source = {'data': {'chart': {'pollAverage': {
            'slug': '/generic-ballot/national/lv-rv-adults',
            'option_candidate_map': {'7': {'123': {'label': 'Democrat'}, '456': {'label': 'Republican'}}},
            'timeseries': [{'date': '2026-10-21Z', 'data': [
                {'cand_id': 456, 'value': 42.8}, {'cand_id': 123, 'value': 50.7}]}]
        }}}}
        flat = []
        def encode(value):
            index = len(flat)
            flat.append(None)
            flat[index] = ({k: encode(v) for k, v in value.items()} if isinstance(value, dict)
                           else [encode(v) for v in value] if isinstance(value, list) else value)
            return index
        encode(source)
        self.assertEqual(ddhq_points(flat), [{'date': '2026-10-21', 'd': 50.7, 'r': 42.8}])

    def test_rcp_follows_headers_not_fixed_column_order(self):
        html = '<table><tr><th>Pollster</th><th>Republicans (R)</th><th>Democrats (D)</th></tr><tr><td>RCP Average</td><td>42.1</td><td>50.4</td></tr></table>'
        self.assertEqual(rcp_observation(html, '2026-10-22T05:00:00+00:00'),
                         {'date': '2026-10-21', 'd': 50.4, 'r': 42.1})

    def test_blocked_or_unidentified_tables_never_become_data(self):
        for html in ['<html>Please enable JS</html>', '<table><tr><td>RCP Average</td><td>50.4</td><td>42.1</td></tr></table>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                rcp_observation(html, '2026-10-22T05:00:00+00:00')


if __name__ == '__main__':
    unittest.main()
