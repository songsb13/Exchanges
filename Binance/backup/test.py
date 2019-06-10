import unittest
from binance import Binance
import asyncio


class BinanceTests(unittest.TestCase):
    def setUp(self):
        self.exchange = Binance('uPRR27c5Ndg0KXSq1CFNTQ3RAvLjLSTet3KNYaiW3eeL9FjU0gluoBoI4MZMTzy0',
                                'VecmWKP2z0GpdPYhGN3T3wGNGSD2Qj4kbLtltzRcfni0Pyo6HHccsPdXqAmCWbOW')

    def tearDown(self):
        pass

    def test_get_exchange_info(self):
        while True:
            info = self.exchange.get_exchange_info()
            if info[0]:
                break

        self.assertTrue('BTC_ETH' in self.exchange.exchange_info)
        self.assertEqual(self.exchange.exchange_info['BTC_ETH'], '0.00100000')

    def test_get_deposit(self):
        self.exchange.get_exchange_info()
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.exchange.get_deposit_addrs())

        self.assertTrue(result[0])
        self.assertTrue(len(result[1]) > 120)

    def test_fee_count(self):
        fc = self.exchange.fee_count()
        self.assertEqual(fc, 1)

    def test_fee(self):
        loop = asyncio.get_event_loop()
        td_fee = loop.run_until_complete(self.exchange.get_trading_fee())
        tx_fee = loop.run_until_complete(self.exchange.get_transaction_fee())

        self.assertTrue(td_fee[0])
        self.assertTrue(tx_fee[0])

        self.assertEqual(td_fee[1], 0.001)
        self.assertTrue(len(tx_fee[1]) > 150)

    def test_balance(self):
        loop = asyncio.get_event_loop()
        bal = loop.run_until_complete(self.exchange.balance())

        self.assertTrue(bal[0])
        self.assertTrue('BTC' in bal[1])

    def test_get_avg_orderbook(self):
        loop = asyncio.get_event_loop()
        orderbook = loop.run_until_complete(self.exchange.get_curr_avg_orderbook(['BTC_ETH']))

        self.assertTrue(orderbook[0])


if __name__ == '__main__':
    unittest.main()

