import unittest
from unittest.mock import patch
from data_api import senate_control


class HouseControlTest(unittest.TestCase):
    @patch('data_api.fetch')
    def test_kalshi_uses_house_republican_contract(self, fetch):
        fetch.return_value = {'markets': [
            {'ticker': 'CONTROLH-2026-D'},
            {'ticker': 'CONTROLH-2026-R', 'event_ticker': 'CONTROLH-2026',
             'yes_bid_dollars': '0.08', 'yes_ask_dollars': '0.10'}]}
        quote = senate_control('kalshi', 'house')
        self.assertEqual(quote['p'], 9)
        self.assertIn('event_ticker=CONTROLH-2026', fetch.call_args.args[0])
        self.assertEqual(quote['series'], 'CONTROLH')

    @patch('data_api.fetch')
    def test_polymarket_selects_republican_yes_by_outcome(self, fetch):
        fetch.return_value = [{'slug': 'which-party-will-win-the-house-in-2026', 'markets': [
            {'groupItemTitle': 'Democratic Party', 'active': True},
            {'groupItemTitle': 'Republican Party', 'active': True, 'closed': False,
             'outcomes': '["No","Yes"]', 'outcomePrices': '["0.915","0.085"]',
             'clobTokenIds': '["democrat","republican"]', 'id': 'house-r'}]}]
        quote = senate_control('polymarket', 'house')
        self.assertEqual(quote['p'], 8.5)
        self.assertEqual(quote['contractSide'], 'R')
        self.assertEqual(quote['token'], 'republican')
        self.assertIn('house-in-2026', fetch.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
