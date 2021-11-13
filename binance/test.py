from Exchanges.binance import binance
from Exchanges.objects import DataStore

from Exchanges.settings import BaseTradeType

import unittest
import asyncio
import threading
import time


class TestBaseBinance(unittest.TestCase):
    """
    tests for execute functions
    """
    @classmethod
    def setUpClass(cls) -> None:
        exchange = binance.Binance(
            'oYQYru6IvzCgxSFaCRdRQyKCHfpUQEEujZAxJsCw5LEjuR7D2F8S7pIGxrN9u2lB ',
            '4WcKtsR88UqGMyYUuKVb7XZlo0adfr8z3eOtZZm4mRWaWTfJTc4prLcZ29Ti8zXl'
        )

        cls.test_main_sai_symbol = 'BTC_TRX'
        cls.exchange = exchange
        available_result = exchange.get_available_symbols()
        cls.available_symbols = available_result.data

        loop = asyncio.new_event_loop()
        transaction_result = loop.run_until_complete(exchange.get_transaction_fee())
        cls.transaction_fees = transaction_result.data

        loop = asyncio.new_event_loop()
        deposit_result = loop.run_until_complete(exchange.get_deposit_addrs(cls.available_symbols))
        cls.deposits = deposit_result.data

        exchange.set_subscriber()
        exchange.set_subscribe_orderbook(cls.available_symbols)
        exchange.set_subscribe_candle(cls.available_symbols)

    def setUp(self) -> None:
        loop = asyncio.new_event_loop()
        result_object = loop.run_until_complete(self.exchange.get_balance())

        self.balance = None if not result_object.success else result_object.data
        print(self.balance)


class TestTradeMarket(TestBaseBinance):
    def test_under_minimum_buy(self):
        minimum = self.exchange._lot_sizes[self.test_main_sai_symbol]['min_quantity']
        test_symbol_minimum_price = self.exchange.buy(

        )

    def test_under_minimum_sell(self):
        pass

    def test_over_balance_buy(self):
        pass

    def test_over_balance_sell(self):
        pass

    def test_no_amount_buy(self):
        pass

    def test_no_amount_sell(self):
        pass

    def test_incorrect_lot_size_buy(self):
        pass

    def test_incorrect_lot_size_sell(self):
        pass


class TestTradeLimit(TestBaseBinance):
    def test_under_minimum_buy(self):
        pass

    def test_under_minimum_sell(self):
        pass

    def test_over_balance_buy(self):
        pass

    def test_over_balance_sell(self):
        pass

    def test_no_amount_buy(self):
        pass

    def test_no_amount_sell(self):
        pass

    def test_incorrect_lot_size_buy(self):
        pass

    def test_incorrect_lot_size_sell(self):
        pass

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
    symbol_set = ['BTC_XRP', 'BTC_ETH', 'BTC_ADA']
    symbol = 'BTC_ADA'
    
    @classmethod
    def setUpClass(cls):
        cls.exchange = binance.Binance(
            'oYQYru6IvzCgxSFaCRdRQyKCHfpUQEEujZAxJsCw5LEjuR7D2F8S7pIGxrN9u2lB ',
            '4WcKtsR88UqGMyYUuKVb7XZlo0adfr8z3eOtZZm4mRWaWTfJTc4prLcZ29Ti8zXl'
        )

    def test_subscribe_orderbook(self):
        time.sleep(1)
        self.exchange.set_subscribe_orderbook(self.symbol)
        for _ in range(20):
            time.sleep(1)
            
    def test_subscribe_candle(self):
        time.sleep(1)
        self.exchange.set_subscribe_candle(self.symbol_set)
        time.sleep(1)

        for _ in range(20):
            time.sleep(1)
    
    def test_subscribe_mix(self):
        time.sleep(1)
        self.exchange.set_subscribe_orderbook(self.symbol)
        time.sleep(1)
        self.exchange.set_subscribe_candle(self.symbol_set)
        for _ in range(20):
            time.sleep(1)

