import requests
import json
import time
import aiohttp
import asyncio
import jwt
import hmac
import json
import asyncio
import base64
import aiohttp

import numpy as np

from pyinstaller_patch import *
from decimal import *
from urllib.parse import urlencode
from datetime import datetime


class BaseExchange(object):
    '''
    all exchanges module should be followed BaseExchange format.
    '''

    #
    _base_url = str
    _key = str
    _secret = str

    def _public_api(self, method, path, extra=None, header=None):
        '''
        For using public API

        :param method: Get or Post
        :param path: URL path without Base URL, '/url/path/'
        :param extra: Parameter if required.
        :param header: Header if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        '''
        pass
    def _private_api(self, method, path, extra=None):
        '''
        For using private API
        :param method: Get or Post
        :param path: URL path without Base URL, '/url/path/'
        :param extra: Parameter if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        '''
        pass

    def _sign_generator(self, *args):
        '''
        :return: signed data example sha256, 512 etc..
        '''
        pass

    def _currencies(self):
        '''
        :return: available currencies, symbol is dependent of each exchange
        '''
        pass

    def fee_count(self):
        '''
        :return: trading fee count, dependent of each exchange.
        example)
        korbit: krw -> btc -> alt, return 2
        upbit: btc -> alt, return 1

        '''
        pass

    def get_ticker(self, market):
        '''
        :return: Ticker data, type is dependent of each exchange.
        '''
        pass

    def get_available_coin(self):
        '''
        :return: Custom symbol list ['BTC_XRP', 'BTC_LTC']
        '''
        pass

    def withdraw(self, coin, amount, to_address, payment_id=None):
        '''
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param to_address: ALT address
        :param payment_id: include if required
        :return: success, data, message, time
        '''
        pass

    def buy(self, coin, amount, price):
        '''
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param price: type is dependent of exchange, common type is str or float. --> 0.001
        :return:
        '''
        pass

    def sell(self, coin, amount, price):
        '''
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param price: type is dependent of exchange, common type is str or float. --> 0.001
        :return:
        '''
        pass

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        '''
        :param currency_pair: BTC_ALT custom symbol.
        :param btc_amount:
        :param alt_amount:
        :param td_fee: trading fee
        :param tx_fee: transaction fee
        :return:
        '''
        pass

    async def _async_public_api(self, method, path, extra=None, header=None):
        '''
        For using async public API

        :param method: Get or Post
        :param path: URL path without Base URL, '/url/path/'
        :param extra: Parameter if required.
        :param header: Header if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        '''
        pass

    async def _async_private_api(self, method, path, extra=None):
        '''
        For using async private API
        :param method: Get or Post
        :param path: URL path without Base URL, '/url/path/'
        :param extra: Parameter if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        '''
        pass

    async def get_deposit_addrs(self, coin_list=None):
        '''
        :param coin_list:
        :return: exchange deposit addrs, type is have to dictonary --> {'BTC': BTCaddrs, ...}
        '''
        pass

    async def get_balance(self):
        '''
        :return: user balance, type is have to dictonary --> {'BTC': float(amount), ...}
        '''
        pass

    async def _get_orderbook(self, symbol):
        '''
        :param market: market must be exchange symbol.
        :return: orderbook, is dependent of each exchange
        '''
        pass

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        '''
        :param coin_list: custom symbol set [BTC_XRP, ...]
        :param btc_sum: be calculate average base on btc_sum
        :return: dict, set of custom symbol with its ask & bid average. {BTC_XRP:{asks:Decimal, bids:Decimal}, ...}
        '''
        pass

    async def compare_orderbook(self, other, coins, default_btc=1):
        '''
        :param other: Other exchange's compare_orderbook object
        :param coins: Custom symbol list --> [BTC_LTC, ...]
        :param default_btc: dfc
        :return: tuple, 2 different exchange orderbook & profit percent of main & sec exchanges
        '''
        pass


