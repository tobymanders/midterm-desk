import unittest
from data_api import race_candidates


def market(label, **extra):
    return {'groupItemTitle': label, 'active': True, 'closed': False,
            'outcomePrices': '[0.5,0.5]', **extra}


class CandidateTest(unittest.TestCase):
    def test_party_labels_and_inactive_options(self):
        self.assertEqual(race_candidates([
            market('Republican'), market('Example Red (R)'),
            market('Example Blue (D)'), market('Withdrawn (D)', closed=True),
        ], 'IA'), [{'name': 'Example Blue', 'party': 'D'},
                   {'name': 'Example Red', 'party': 'R'}])

    def test_alaska_uses_the_named_senator(self):
        self.assertEqual(race_candidates([
            market('Dan Sullivan'), market('Mary Peltola'), market('Sen. Dan Sullivan')
        ], 'AK'), [{'name': 'Mary Peltola', 'party': 'D'},
                   {'name': 'Dan Sullivan', 'party': 'R'}])

    def test_nebraska_independent_is_not_democrat(self):
        self.assertEqual(race_candidates([market('Independent'), market('Democrat')], 'NE'),
                         [{'name': 'Dan Osborn', 'party': 'I'}])


if __name__ == '__main__':
    unittest.main()
