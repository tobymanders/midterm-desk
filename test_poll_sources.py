import unittest
from poll_sources import ddhq_points


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



if __name__ == '__main__':
    unittest.main()
