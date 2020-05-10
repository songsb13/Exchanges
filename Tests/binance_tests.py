import unittest
from Exchanges.Binance import binance
import asyncio
import time


class TestNotification(unittest.TestCase):
    symbol_set = ['BTC_ETH', 'BTC_XRP']
    @classmethod
    def setUpClass(cls):
        cls.exchange = binance.Binance(
            'oYQYru6IvzCgxSFaCRdRQyKCHfpUQEEujZAxJsCw5LEjuR7D2F8S7pIGxrN9u2lB ',
            '4WcKtsR88UqGMyYUuKVb7XZlo0adfr8z3eOtZZm4mRWaWTfJTc4prLcZ29Ti8zXl'
        )

    def test_exchange_info(self):
        # get default info for taking deposit fee and etc..
        result = self.exchange._get_exchange_info()
        self.assertTrue(result.success)
        self.assertIn(
            'BTC_ETH',
            sorted(list(result.data.keys()))
        )
        self.assertEqual(result.data.get('BTC_ETH'), '0.001')
    
    def test_get_candle(self):
        result = self.exchange.get_candle("BTC_XRP", 1, 199)
        self.assertTrue(result.success)
        self.assertEqual(len(result.data['timestamp']), 199)
    
    def test_get_deposit_addrs(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.exchange.get_deposit_addrs())
        self.assertTrue(result.success)
        self.assertIn('BTC', result.data)
        print(result.data)
    
    def test_get_transaction_fee(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.exchange.get_transaction_fee())
        self.assertTrue(result.success)
        self.assertIn('BTC', result.data)
        print(result.data)

    def test_get_balance(self):
        loop = asyncio.get_event_loop()
        balance_result = loop.run_until_complete(self.exchange.get_balance())
        self.assertTrue(balance_result.success)
        self.assertIn('BTC', balance_result.data)
        print(balance_result.data)
    
    def test_get_avg_price(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.exchange.get_avg_price(self.symbol_set))
        self.assertTrue(result.success)
        self.assertIn('BTC', result.data)
        print(result.data)
    
    def test_trade(self):
        buy_result = self.exchange.buy('BTC_XRP', 1)
        self.assertTrue(buy_result.success)
        self.assertEqual(1, buy_result.data.get('qty'))
        sell_result = self.exchange.sell('BTC_XRP', 1)
        self.assertTrue(sell_result.success)
        self.assertEqual(1, sell_result.data.get('qty'))

    def test_servertime(self):
        servertime_result = self.exchange
        print(time.time() - float(servertime_result.data))
