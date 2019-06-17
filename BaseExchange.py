import requests
import json
import time
import aiohttp
import numpy as np
import asyncio

from urllib.parse import urlencode
from decimal import *


class BaseExchange:
    '''
    all exchanges should be followed BaseExchange format.
    '''

    #
    _base_url = str
    _key = str
    _secret = str

    def _public_api(self, method, path, extra=None, header=None):
        '''
        For using public API

        :param method: Get or Post
        :param path: URL path do not contain Base URL, '/url/path/'
        :param extra: Parameter if required.
        :param header: Header if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        '''

    def _private_api(self, method, path, extra=None):
        '''
        For using private API
        :param method: Get or Post
        :param path: URL path do not contain Base URL, '/url/path/'
        :param extra: Parameter if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        '''

    def _sign_generator(self, *args):
        '''
        :return: signed data
        '''

    def _currencies(self):
        '''
        :return: available currencies in exchange, symbol is dependent of each exchange
        '''

    def fee_count(self):
        '''
        :return: trading fee count, dependent of each exchange.
        example)
        korbit: krw -> btc -> alt, return 2
        upbit: btc -> alt, return 1

        '''
        # 몇변의 수수료가 산정되는지

    def get_ticker(self, market):
        '''
        :return: Ticker data, type is dependent of each exchange.
        '''

    def get_available_coin(self):
        '''
        :return: Custom symbol list ['BTC_XRP', 'BTC_LTC']
        '''

    def withdraw(self, coin, amount, to_address, payment_id=None):
        '''
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param to_address: ALT address
        :param payment_id: include if required
        :return: success, data, message, time
        '''

    def buy(self, coin, amount, price):
        '''
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param price: type is dependent of exchange, common type is str or float. --> 0.001
        :return:
        '''
        amount, price = map(str, (amount, price * 1.05))

        params = {
            'market': coin,
            'side': 'bid',
            'volume': amount,
            'price': price,
            'ord_type': 'limit'
        }

        return self._private_api('POST', 'orders', params)

    def sell(self, coin, amount, price):
        '''
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param price: type is dependent of exchange, common type is str or float. --> 0.001
        :return:
        '''
        amount, price = map(str, (amount, price * 0.95))

        params = {
            'market': coin,
            'side': 'ask',
            'volume': amount,
            'price': price,
            'ord_type': 'limit'
        }

        return self._private_api('POST', 'orders', params)

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        '''
        :param currency_pair: BTC_ALT custom symbol.
        :param btc_amount:
        :param alt_amount:
        :param td_fee: trading fee
        :param tx_fee: transaction fee
        :return:
        '''
        # after self.buy()
        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return True, alt_amount, ''

    # def alt_to_base(self, currency_pair, btc_amount, alt_amount):
    # '''
    # :param currency_pair: BTC_ALT custom symbol.
    # :param btc_amount:
    # :param alt_amount:
    # :param td_fee: trading fee
    # :param tx_fee: transaction fee
    # :return:
    # '''
    #     # after self.sell()
    #     if suc:
    #         upbit_logger.info('AltToBase 성공')
    #
    #         return True, '', data, 0
    #
    #     else:
    #         upbit_logger.info(msg)
    #
    #         if '부족합니다.' in msg:
    #             alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
    #             continue

    async def _async_public_api(self, method, path, extra=None, header=None):
        '''
        For using async public API

        :param method: Get or Post
        :param path: URL path do not contain Base URL, '/url/path/'
        :param extra: Parameter if required.
        :param header: Header if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        '''

    async def _async_private_api(self, method, path, extra=None):
        '''
        For using async private API
        :param method: Get or Post
        :param path: URL path do not contain Base URL, '/url/path/'
        :param extra: Parameter if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        '''

    async def get_deposit_addrs(self, coin_list=None):
        '''
        :param coin_list: ?
        :return: exchange deposit addrs, type is have to dictonary --> {'BTC': BTCaddrs, ...}
        '''

    async def get_balance(self):
        '''
        :return: user balance, type is have to dictonary --> {'BTC': float(amount), ...}
        '''

    async def get_orderbook(self, symbol):
        '''
        :param market: market must be exchange symbol.
        :return:
        '''

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        '''
        :param coin_list:
        :param btc_sum:
        :return:
        '''
        avg_order_book = {}
        for coin in coin_list:
            coin = coin.replace('_', '-')
            suc, book, msg = await self.get_orderbook(coin)

            if not suc:
                return False, '', msg

            avg_order_book[coin] = {}

            for type_ in ['ask', 'bid']:
                order_amount, order_sum = [], 0

                for data in book[0]['orderbook_units']:
                    size = data['{}_size'.format(type_)]
                    order_amount.append(size)
                    order_sum += data['{}_price'.format(type_)] * size

                    if order_sum >= btc_sum:
                        volume = order_sum / np.sum(order_amount)
                        avg_order_book[coin]['{}s'.format(type_)] = Decimal(volume).quantize(Decimal(10) ** -8)

                        break

            return True, avg_order_book, ''

    async def compare_orderbook(self, other, coins, default_btc=1):
        '''
        :param other: Other exchange's compare_orderbook object
        :param coins: Custom symbol list --> [BTC_LTC, ...]
        :param default_btc: dfc
        :return:
        '''
        upbit_res, other_res = await asyncio.gather(
            self.get_curr_avg_orderbook(coins, default_btc),
            other.get_curr_avg_orderbook(coins, default_btc)
        )

        u_suc, u_orderbook, u_msg = upbit_res
        o_suc, o_orderbook, o_msg = other_res

        if u_suc and o_suc:
            m_to_s = {}
            for currency_pair in coins:
                m_ask = u_orderbook[currency_pair]['asks']
                s_bid = o_orderbook[currency_pair]['bids']
                m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

            s_to_m = {}
            for currency_pair in coins:
                m_bid = u_orderbook[currency_pair]['bids']
                s_ask = o_orderbook[currency_pair]['asks']
                s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

            res = u_orderbook, o_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m}

            return True, res, ''

