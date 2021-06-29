from Exchanges.binance import binance
from Exchanges.objects import DataStore

import unittest
import asyncio
import threading
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
        print(result.data)
        self.assertIn(
            'BTC_ETH',
            sorted(list(result.data.keys()))
        )

    def test_get_available_coin(self):
        result = self.exchange.get_available_coin()
        self.assertTrue(result.success)
        self.assertIn('BTC_XRP', result.data)
        print(result.data)
    
    def test_get_candle(self):
        result = self.exchange.get_candle(self.symbol_set, 1)
        self.assertTrue(result.success)
        print(result.data)
        self.assertEqual(len(result.data['timestamp']), 20)
    
    def test_get_orderbook(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.exchange.get_curr_avg_orderbook(self.symbol_set))
        self.assertTrue(result.success)
        print(result.data)
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
    
    def test_market_trade(self):
        converted_coin = self.exchange._sai_symbol_converter('BTC_XRP')
        buy_result = self.exchange.buy(converted_coin, 5)
        if buy_result.success:
            print(buy_result.data)
        else:
            print(buy_result.message)
        self.assertTrue(buy_result.success)
        
        sell_result = self.exchange.sell(converted_coin, 5)
        if sell_result.success:
            print(sell_result.data)
        else:
            print(sell_result.message)
        self.assertTrue(sell_result.success)

    def test_servertime(self):
        servertime_result = self.exchange
        print(time.time() - float(servertime_result.data))


class BinanceSocketTest(unittest.TestCase):
    symbol_set = ['ethbtc', 'xrpbtc']
    symbol = 'btcusdt'
    
    @classmethod
    def setUpClass(cls):
        cls.exchange = binance.BinanceSubscriber(
            DataStore(),
            dict(orderbook=threading.Lock(), candle=threading.Lock())
        )
        
    def test_subscribe_orderbook(self):
        self.orderbook_subscriber = threading.Thread(target=self.exchange.run_forever, daemon=True)
        self.orderbook_subscriber.start()
        time.sleep(1)
        self.exchange.subscribe_orderbook(self.symbol_set)
        time.sleep(10)
        self.exchange.unsubscribe_orderbook(self.symbol)
        
        for _ in range(60):
            time.sleep(1)
            
    def test_subscribe_candle(self):
        self.candle_subscriber = threading.Thread(target=self.exchange.run_forever, daemon=True)
        self.candle_subscriber.start()
        time.sleep(1)
        self.exchange.subscribe_candle(self.symbol_set)

        for _ in range(60):
            time.sleep(1)
    
    def test_subscribe_mix(self):
        self.subscriber = threading.Thread(target=self.exchange.run_forever, daemon=True)
        self.subscriber.start()
        time.sleep(1)
        self.exchange.subscribe_candle(self.symbol_set)
        time.sleep(10)
        
        for _ in range(60):
            time.sleep(1)

