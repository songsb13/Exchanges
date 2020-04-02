import unittest
from Exchanges.ByBit import bybit
import asyncio
import time


class TestNotification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exchange = bybit.ByBit('UOzp4ca4rYRHF7sn9N', '5cyMD5cFR28wFPdkiN0vOjjGoKNzN1XSZ4XU')

    def test_exchange_info(self):
        result = self.exchange._get_exchange_info()
        self.assertEqual(len(result.data), 4)
        self.assertEqual(
            sorted(list(result.data.keys())),
            sorted(['USD_BTC', 'USD_ETH', 'USD_XRP', 'USD_EOS'])
        )
        self.assertEqual(result.data.get('USD_BTC'), '0.5')
        self.assertEqual(result.data.get('USD_ETH'), '0.05')
        self.assertEqual(result.data.get('USD_XRP'), '0.0001')
        self.assertEqual(result.data.get('USD_EOS'), '0.001')

    def test_get_candle(self):
        result = self.exchange.get_candle("USD_BTC", 1, 199)
        self.assertTrue(result.success)
        self.assertEqual(len(result.data['timestamp']), 199)

    def test_get_balance(self):
        loop = asyncio.get_event_loop()
        balance_result = loop.run_until_complete(self.exchange.balance())
        self.assertIn('BTC', balance_result.data)

    def test_trade(self):
        buy_result = self.exchange.buy('USD_BTC', 1)
        self.assertTrue(buy_result.success)
        self.assertEqual(1, buy_result.data.get('qty'))
        sell_result = self.exchange.sell('USD_BTC', 1)
        self.assertTrue(sell_result.success)
        self.assertEqual(1, sell_result.data.get('qty'))

    def test_servertime(self):
        servertime_result = self.exchange.servertime()
        print(time.time() - float(servertime_result.data))
