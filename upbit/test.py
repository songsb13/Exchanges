from Exchanges.upbit import upbit
from Exchanges.objects import DataStore

import threading
import unittest
import asyncio
import time


class TestNotification(unittest.TestCase):
    symbol_set = ['BTC_ETH', 'BTC_XRP']
    
    @classmethod
    def setUpClass(cls):
        cls.exchange = upbit.BaseUpbit(
            key='qfbl7FNHhPbXgGhJVSDaoJMxXcJnphhDoDLnugNk4QI ',
            secret='wIvD1OOUYMxXONNB7biRjUtltTDY9hcD1BlFO6IqVx6'
        )
    
    def test_get_available_coin(self):
        result = self.exchange.get_available_coin()
        self.assertTrue(result.success)
        self.assertIn('BTC_XRP', result.data)
        print(result.data)
    
    def test_get_curr_avg_orderbook(self):
        loop = asyncio.get_event_loop()
        while True:
            result = loop.run_until_complete(self.exchange.get_curr_avg_orderbook(''))
            print(result.__dict__)
            time.sleep(1)
    
    def test_get_balance(self):
        loop = asyncio.get_event_loop()
        balance_result = loop.run_until_complete(self.exchange.get_balance())
        self.assertTrue(balance_result.success)
        self.assertIn('BTC', balance_result.data)
        print(balance_result.data)
    
    def test_get_candle(self):
        while True:
            result = self.exchange.get_candle()
            print(result.__dict__)
            time.sleep(1)
    
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
    
    def test_get_avg_price(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.exchange.get_avg_price(self.symbol_set))
        self.assertTrue(result.success)
        self.assertIn('BTC', result.data)
        print(result.data)
    
    def test_market_trade(self):
        converted_coin = self.exchange._sai_to_upbit_symbol_converter('BTC_XRP')
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


class UpbitSocketTest(unittest.TestCase):
    symbol_set = ['BTC_ETH', 'BTC_XRP']
    symbol = 'BTC_ETH'
    
    @classmethod
    def setUpClass(cls):
        cls.exchange = upbit.BaseUpbit(
            key='qfbl7FNHhPbXgGhJVSDaoJMxXcJnphhDoDLnugNk4QI ',
            secret='wIvD1OOUYMxXONNB7biRjUtltTDY9hcD1BlFO6IqVx6'
        )

    def test_subscribe_orderbook(self):
        time.sleep(1)

        self.exchange.set_subscribe_orderbook(self.symbol)

        for _ in range(20):
            time.sleep(1)

    def test_subscribe_candle(self):
        time.sleep(1)

        self.exchange.set_subscribe_candle(self.symbol_set)

        for _ in range(20):
            time.sleep(1)
    
    def test_subscribe_mix(self):
        time.sleep(1)

        self.exchange.set_subscribe_orderbook(self.symbol_set)
        time.sleep(1)
        self.exchange.set_subscribe_candle(self.symbol)
        for _ in range(20):
            time.sleep(1)

