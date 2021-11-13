from Exchanges.upbit import upbit
from Exchanges.objects import DataStore

from Exchanges.settings import BaseTradeType
from Exchanges.upbit.setting import LocalConsts

from decimal import Decimal, ROUND_DOWN
import threading
import unittest
import asyncio
import time



class TestBaseUpbit(unittest.TestCase):
    """
        tests for execute functions -> trading, withdraw
    """
    @classmethod
    def setUpClass(cls) -> None:
        exchange = upbit.BaseUpbit(
            key='',
            secret=''
        )
        cls.test_main_sai_symbol = 'KRW_BTC'
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


class TestTradeMarket(TestBaseUpbit):
    def test_under_minimum_buy(self):
        krw_btc_minimum_price = LocalConsts.LOT_SIZES['KRW']['minimum'] * 0.9
        trading_result = self.exchange.buy(self.test_main_sai_symbol, BaseTradeType.BUY_MARKET,
                                           price=krw_btc_minimum_price)
        self.assertFalse(trading_result.success)
    
    def test_under_minimum_sell(self):
        result = self.exchange.get_ticker(self.test_main_sai_symbol)
        self.assertTrue(result.success)
    
        krw_btc_price = result.data['sai_price']
    
        krw_btc_minimum_price = LocalConsts.LOT_SIZES['KRW']['minimum'] * 0.9
    
        amount = Decimal(krw_btc_minimum_price / krw_btc_price).quantize(Decimal(10) ** -8, rounding=ROUND_DOWN)

        trading_result = self.exchange.sell(self.test_main_sai_symbol, BaseTradeType.SELL_MARKET,
                                            amount=amount)
        self.assertFalse(trading_result.success)

    def test_over_balance_buy(self):
        krw_over_balance = self.balance['KRW'] * 1.5
        trading_result = self.exchange.buy(self.test_main_sai_symbol, BaseTradeType.BUY_MARKET,
                                           price=krw_over_balance)
        self.assertFalse(trading_result.success)

    def test_over_balance_sell(self):
        result = self.exchange.get_ticker(self.test_main_sai_symbol)
        self.assertTrue(result.success)
    
        krw_btc_price = result.data['sai_price']
    
        krw_over_balance = self.balance['KRW'] * 1.5
    
        amount = Decimal(krw_over_balance / krw_btc_price).quantize(Decimal(10) ** -8, rounding=ROUND_DOWN)
    
        trading_result = self.exchange.sell(self.test_main_sai_symbol, BaseTradeType.SELL_MARKET,
                                            amount=amount)
        self.assertFalse(trading_result.success)

    def test_no_amount_buy(self):
        empty_price = 0
        trading_result = self.exchange.buy(self.test_main_sai_symbol, BaseTradeType.BUY_MARKET,
                                           price=empty_price)

        self.assertFalse(trading_result.success)

    def test_no_amount_sell(self):
        empty_amount = 0
        trading_result = self.exchange.sell(self.test_main_sai_symbol, BaseTradeType.SELL_MARKET,
                                            amount=empty_amount)
        self.assertFalse(trading_result.success)

    def test_incorrect_lot_size_buy(self):
        trading_price = LocalConsts.LOT_SIZES['KRW'] * 0.5
        trading_result = self.exchange.buy(self.test_main_sai_symbol, BaseTradeType.BUY_MARKET,
                                           price=trading_price)

        self.assertFalse(trading_result.success)

    def test_incorrect_lot_size_sell(self):
        trading_price = LocalConsts.LOT_SIZES['KRW'] * 0.5
        trading_result = self.exchange.buy(self.test_main_sai_symbol, BaseTradeType.BUY_MARKET,
                                           price=trading_price)

        self.assertFalse(trading_result.success)


class TestTradeLimit(TestBaseUpbit):
    def test_under_minimum_buy(self):
        result = self.exchange.get_ticker(self.test_main_sai_symbol)
        self.assertTrue(result.success)

        krw_btc_price = result.data['sai_price']

        krw_btc_minimum_price = LocalConsts.LOT_SIZES['KRW']['minimum'] * 0.9

        amount = Decimal(krw_btc_minimum_price / krw_btc_price).quantize(Decimal(10) ** -8, rounding=ROUND_DOWN)

        trading_result = self.exchange.buy(self.test_main_sai_symbol, BaseTradeType.BUY_LIMIT,
                                           amount=amount, price=krw_btc_price)

        self.assertFalse(trading_result.success)

    def test_under_minimum_sell(self):
        result = self.exchange.get_ticker(self.test_main_sai_symbol)
        self.assertTrue(result.success)

        krw_btc_price = result.data['sai_price']

        krw_btc_minimum_price = LocalConsts.LOT_SIZES['KRW']['minimum'] * 0.9

        amount = Decimal(krw_btc_minimum_price / krw_btc_price).quantize(Decimal(10) ** -8, rounding=ROUND_DOWN)

        trading_result = self.exchange.sell(self.test_main_sai_symbol, BaseTradeType.SELL_LIMIT,
                                            amount=amount, price=krw_btc_price)

        self.assertFalse(trading_result.success)

    def test_over_balance_buy(self):
        result = self.exchange.get_ticker(self.test_main_sai_symbol)
        self.assertTrue(result.success)

        krw_btc_price = result.data['sai_price']

        krw_over_balance = self.balance['KRW'] * 1.5

        amount = Decimal(krw_over_balance / krw_btc_price).quantize(Decimal(10) ** -8, rounding=ROUND_DOWN)

        trading_result = self.exchange.buy(self.test_main_sai_symbol, BaseTradeType.BUY_LIMIT,
                                           amount=amount, price=krw_btc_price)
        self.assertFalse(trading_result.success)

    def test_over_balance_sell(self):
        result = self.exchange.get_ticker(self.test_main_sai_symbol)
        self.assertTrue(result.success)

        krw_btc_price = result.data['sai_price']

        krw_over_balance = self.balance['KRW'] * 1.5

        amount = Decimal(krw_over_balance / krw_btc_price).quantize(Decimal(10) ** -8, rounding=ROUND_DOWN)

        trading_result = self.exchange.sell(self.test_main_sai_symbol, BaseTradeType.SELL_MARKET,
                                            amount=amount, price=krw_btc_price)
        self.assertFalse(trading_result.success)

    def test_no_amount_buy(self):
        empty_amount = 0
        empty_price = 0
        trading_result = self.exchange.buy(self.test_main_sai_symbol, BaseTradeType.BUY_LIMIT,
                                           amount=empty_amount, price=empty_price)

        self.assertFalse(trading_result.success)

    def test_no_amount_sell(self):
        empty_amount = 0
        empty_price = 0
        trading_result = self.exchange.sell(self.test_main_sai_symbol, BaseTradeType.SELL_LIMIT,
                                            amount=empty_amount, price=empty_price)

        self.assertFalse(trading_result.success)


class TestWithdraw(TestBaseUpbit):
    def test_under_minimum(self):
        pass

    def test_under_balance(self):
        pass

    def test_over_balance(self):
        pass

    def test_no_amount(self):
        pass

    def test_incorrect_step_size(self):
        pass

    def test_incorrect_lot_size(self):
        pass


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

