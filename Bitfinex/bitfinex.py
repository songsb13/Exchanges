import json
import base64
import hmac
import hashlib
import requests
import time
import aiohttp
import asyncio
from decimal import Decimal, ROUND_DOWN

from Exchanges.base_exchange import BaseExchange, ExchangeResult
from Util.pyinstaller_patch import *


class Bitfinex(BaseExchange):
    def __init__(self, *args, **kwargs):
        '''
            :param key: input your upbit key
            :param secret: input your upbit secret
        '''
        self._base_url = 'https://api.bitfinex.com'
        self._public_base_url = 'https://api-pub.bitfinex.com'
        self.name = 'bitfinex'
        
        if kwargs:
            self._key = kwargs['key']
            self._secret = kwargs['secret']

        self._symbol_full_name = {}

    def _sign_generator(self, *args):
        payload, *_ = args
        j = json.dumps(payload) if payload else ''
        data = base64.standard_b64encode(j.encode('utf8'))

        hmc = hmac.new(self._secret.encode('utf8'), data, hashlib.sha384)
        signature = hmc.hexdigest()
        return {
            "X-BFX-APIKEY": self._key,
            "X-BFX-SIGNATURE": signature,
            "X-BFX-PAYLOAD": data.decode('utf-8')
        }

    def _symbol_customizing(self, symbol):
        # change qtm, iot, dsh to customized symbol
        actual_symbol = dict(
            qtm='qtum',
            iot='iota',
            dsh='dash'
        )
        return actual_symbol.get(symbol)

    def _symbol_localizing(self, symbol):
        # change customized symbol to local use symbol
        actual_symbol = dict(
            QTUM='QTM',
            IOTA='IOT',
            DASH='DSH'
        )
        return actual_symbol.get(symbol)

    def _get_symbol_full_name(self):
        for _ in range(3):
            res_object = self._public_api('/v2/conf/pub:map:currency:label')

            if res_object.success is False:
                time.sleep(res_object.wait_time)
                continue
            dic = {each[0]: each[1] for each in res_object.data[0]}

            res_object.data = self._symbol_full_name = dic

        return res_object

    def _public_api(self, path, extra=None):
        debugger.debug('[{}]Parameters=[{}, {}], function name=[_public_api]'.format(self.name, path, extra))

        try:
            if extra is None:
                extra = dict()

            path = self._base_url + path
            rq = requests.get(path, params=extra)
            response = rq.json()

            if 'message' in response:
                error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['message'], path, extra)
                debugger.debug(error_message)
                return ExchangeResult(False, '', error_message, 1)
            elif 'error' in response:
                error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['error'], path, extra)
                debugger.debug(error_message)
                return ExchangeResult(False, '', error_message, 1)
            else:
                return ExchangeResult(True, response, '', 0)
                
        except Exception as ex:
            error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, ex, path, extra)
            debugger.debug(error_message)
            return ExchangeResult(False, '', error_message, 1)

    def _private_api(self, path, extra=None):
        debugger.debug('[{}]Parameters=[{}, {}], function name=[_private_api]'.format(self.name, path, extra))

        try:
            if extra is None:
                extra = dict()
            url = self._base_url + path

            extra['request'] = path
            extra['nonce'] = str(time.time())

            sign_ = self._sign_generator(extra)

            rq = requests.post(url, json=extra, headers=sign_)

            response = rq.json()

            if 'message' in response:
                error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['message'], path, extra)
                debugger.debug(error_message)
                return ExchangeResult(False, '', error_message, 1)
            elif 'error' in response:
                error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['error'], path, extra)
                debugger.debug(error_message)
                return ExchangeResult(False, '', error_message, 1)
            else:
                return ExchangeResult(True, response, '', 0)
        except Exception as ex:
            error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, ex, path, extra)
            debugger.debug(error_message)
            return ExchangeResult(False, '', error_message, 1)

    def _currencies(self):
        for _ in range(3):
            res_object = self._public_api('/v1/symbols')

            if res_object.success:
                break
            time.sleep(res_object.wait_time)

        return res_object
    
    def _sai_symbol_converter(self, symbol):
        # BTC_XRP -> XRPBTC
        return ''.join(symbol.split('_')[::-1])
    
    def get_precision(self, pair=None):
        return ExchangeResult(True, (-8, -8), '', 0)

    def get_ticker(self, market):
        # 30 req/min
        for _ in range(3):
            symbol = self._sai_symbol_converter(market)
            res_object = self._public_api('/pubticker', {'pair': symbol})

            if res_object.success:
                res_object.data = float(res_object.data['last_price'])
                break
                
        return res_object
        
    def buy(self, market, quantity, price=None):
        debugger.debug('[{}]Parameters=[{}, {}, {}], function name=[buy]'.format(self.name, market, quantity, price))

        price = 1 if price is None else price

        amount, price = [str(Decimal(data).quantize(Decimal(10) ** -8)) for data in [quantity, price]]
        market_type = 'market' if price is None else 'limit'

        params = {
            'symbol': market,
            'amount': amount,
            'side': 'buy',
            'type': market_type,
            'price': price
        }

        return self._private_api('/v1/order/new', params)

    def sell(self, market, quantity, price=None):
        debugger.debug('[{}]Parameters=[{}, {}, {}], function name=[sell]'.format(self.name, market, quantity, price))

        amount, price = [str(Decimal(data).quantize(Decimal(10) ** -8)) for data in [quantity, price]]
        market_type = 'market' if price is None else 'limit'

        params = {
            'symbol': market,
            'amount': amount,
            'side': 'sell',
            'type': market_type,
            'price': price
        }

        return self._private_api('/v1/order/new', params)

    def withdraw(self, coin, amount, to_address, payment_id=None):
        debugger.debug('[{}]Parameters=[{}, {}, {}, {}], function name=[sell]'.format(self.name, coin, amount,
                                                                                      to_address, payment_id))
        if not self._symbol_full_name:
            # 로직 상 deposit_addrs에서 값이 지정됨.
            result_object = self._get_symbol_full_name()

            if result_object.success is False:
                return result_object

        with_type = self._symbol_full_name[coin.upper()]

        params = {
            'withdraw_type': with_type,
            'walletselected': 'exchange',
            'amount': amount,
            'address': to_address
        }

        if payment_id:
            params['payment_id'] = payment_id

        return self._private_api('/v1/withdraw', params)

    def get_available_coin(self):
        result_object = self._currencies()

        if result_object.success:
            available_list = []

            for coin in result_object.data:
                if coin.endswith('btc'):
                    alt = self._symbol_customizing(coin[:-3]) if coin.startswith(('qtm', 'dsh', 'iot')) else coin[:-3]
                    available_list.append('BTC_{}'.format(alt.upper()))

            result_object.data = available_list

        return result_object

    def base_to_alt(self, currency, tradable_btc, alt_amount, td_fee, tx_fee):
        symbol = self._sai_symbol_converter(currency)
        base_market, coin = currency.split('_')
        result_object = self.buy(symbol.lower(), alt_amount)
        if result_object:
            alt = alt_amount
            alt *= ((1 - Decimal(td_fee)) ** 1)
            alt -= Decimal(tx_fee[coin])
            alt = alt.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

            result_object.data = alt

        return result_object

    def alt_to_base(self, currency, tradable_btc, alt_amount):
        base_market, coin = currency.split('_')
        symbol = coin + base_market
        return self.sell(symbol.lower(), alt_amount)

    async def _async_public_api(self, path, extra=None):
        debugger.debug('[{}]Parameters=[{}, {}], function name=[_async_public_api]'.format(self.name, path, extra))

        if extra is None:
            extra = dict()

        try:
            url = self._base_url + path
            async with aiohttp.ClientSession() as sync:
                rq = await sync.get(url, params=extra)
                response = json.loads(await rq.text())

                if 'message' in response:
                    error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['message'], path, extra)
                    debugger.debug(error_message)
                    return ExchangeResult(False, '', error_message, 1)
                elif 'error' in response:
                    error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['error'], path, extra)
                    debugger.debug(error_message)
                    return ExchangeResult(False, '', error_message, 1)
                else:
                    return ExchangeResult(True, response, '', 1)
        except Exception as ex:
            error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, ex, path, extra)
            debugger.debug(error_message)
            return ExchangeResult(False, '', error_message, 1)

    async def _async_private_api(self, method, path, extra=None):
        debugger.debug('[{}]Parameters=[{}, {}, {}], function name=[_async_private_api]'.format(self.name, method, path, extra))

        if extra is None:
            extra = dict()

        try:
            url = self._base_url + path
            async with aiohttp.ClientSession() as sync:
                extra['request'] = path
                extra['nonce'] = str(time.time())

                sign_ = self._sign_generator(extra)

                rq = await sync.post(url, data=extra, headers=sign_)

                response = json.loads(await rq.text())

                if 'message' in response:
                    error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['message'], path, extra)
                    debugger.debug(error_message)
                    return ExchangeResult(False, '', error_message, 1)
                elif 'error' in response:
                    error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['error'], path, extra)
                    debugger.debug(error_message)
                    return ExchangeResult(False, '', error_message, 1)
                else:
                    return ExchangeResult(True, response, '', 0)
        except Exception as ex:
            error_message = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, ex, path, extra)
            debugger.debug(error_message)
            return ExchangeResult(False, '', error_message, 1)

    async def _get_balance(self):
        for _ in range(3):
            result_object = await self._async_private_api('POST', '/v1/balances')

            if result_object.success:
                break

            time.sleep(result_object.wait_time)

        return result_object

    async def _get_orderbook(self, coin):
        # 30 req/min
        for _ in range(3):
            # For Trading: if AMOUNT > 0 then bid else ask.
            result_object = await self._async_public_api('/v2/book/t{}/P0'.format(coin))

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def _get_deposit_addrs(self, currency):
        if currency == 'ethereum classic':
            currency = 'ethereumc'
            
        params = {
            'method': currency,
            'wallet_name': 'exchange',

        }

        for _ in range(3):
            result_object = await self._async_private_api('POST', '/v1/deposit/new', params)
            
            if result_object.success:
                break
            time.sleep(result_object.wait_time)
            
        return result_object
        
    async def _get_trading_fee(self, symbol):
        for _ in range(3):
            result_object = await self._async_private_api('POST', '/v1/account_infos')

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def _get_transaction_fee(self, symbol):
        for _ in range(3):
            result_object = await self._async_private_api('POST', '/v1/account_fees')

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def get_balance(self):
        result_object = await self._get_balance()

        if result_object.data:
            # 밸런스가 없는경우
            result_object.data = {value['currency'].lower(): float(value['amount']) for value in result_object.data if
                                  value['type'] == 'exchange'}
        else:
            result_object.message = 'ERROR_BODY=[밸런스가 없습니다.], URL=[/v1/balances]'

        return result_object

    async def get_deposit_addrs(self, coin_list=None):
        # wallet name이 지정되어 있어야 한다.
        if not self._symbol_full_name:
            result_object = self._get_symbol_full_name()

            if result_object.success is False:
                return result_object

        coin_set_object = self.get_available_coin()

        if coin_set_object.success:
            coins = dict()
            for currency in coin_set_object.data:
                time.sleep(0.05)
                currency = currency.split('_')[1]

                if currency in ['QTUM', 'DASH', 'IOTA']:
                    currency = self._symbol_localizing(currency)

                if currency not in self._symbol_full_name:
                    continue

                deposit_object = await self._get_deposit_addrs(self._symbol_full_name[currency].lower())
                if not deposit_object.success:
                    if 'Unknown method' in deposit_object.message:
                        continue

                    return deposit_object

                upper_currency = currency.upper()

                if currency in ['XRP', 'XMR']:
                    coins['{}TAG'.format(upper_currency)] = deposit_object.data['address']
                    coins[upper_currency] = deposit_object.data['address_pool']

                else:
                    coins[upper_currency] = deposit_object.data['address']

            coin_set_object.data = coins

        return coin_set_object

    async def get_trading_fee(self):
        result_object = await self._get_trading_fee(symbol=None)
        # self.last_retrieve_time = time.time()
        if result_object.success:
            if result_object.data:
                result_object.data = float(result_object.data[0]['taker_fees']) / 100.0
            else:
                result_object.message = 'ERROR_BODY=[Data is not exist]'

        return result_object

    async def get_transaction_fee(self):
        result_object = await self._get_transaction_fee(symbol=None)

        if result_object.success:
            dic_ = dict()
            data = result_object.data['withdraw']
            for key_ in data:
                processing_key = self._symbol_customizing(key_.lower()).upper() \
                    if key_ in ['QTM', 'DSH', 'IOT'] else key_

                dic_[processing_key] = float(result_object.data[key_])

        return result_object

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        avg_orderbook = dict()
        for pair in coin_list:
            base_market, coin = pair.split('_')

            if coin in ['QTUM', 'DASH', 'IOTA']:
                coin = self._symbol_localizing(coin)

            symbol = (coin + base_market).lower()
            orderbook_object = await self._get_orderbook(symbol)
            if not orderbook_object.success:
                return orderbook_object

            avg_orderbook[pair] = dict()
            for order_type in ['asks', 'bids']:
                sum_ = Decimal(0.0)
                total_coin_num = Decimal(0.0)
                for data in orderbook_object.data[order_type]:
                    price = data['price']
                    alt_coin_num = data['amount']
                    sum_ += Decimal(price) * Decimal(alt_coin_num)
                    total_coin_num += Decimal(alt_coin_num)
                    if sum_ > btc_sum:
                        break
                avg_orderbook[pair][order_type] = (sum_/total_coin_num).quantize(Decimal(10) ** -8)

        orderbook_object.data = avg_orderbook

        return orderbook_object

    async def compare_orderbook(self, other, currency_pairs=None, default_btc=1):
        if currency_pairs is None:
            currency_pairs = list()

        for _ in range(3):
            bitfinex_object, other_object = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs, default_btc),
                                                                 other.get_curr_avg_orderbook(currency_pairs, default_btc))

            is_success = (bitfinex_object.success and other_object.success)

            if is_success:
                m_to_s, s_to_m = dict(), dict()

                for currency_pair in currency_pairs:
                    m_ask = bitfinex_object.data[currency_pair]['asks']
                    s_bid = other_object.data[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                    m_bid = bitfinex_object.data[currency_pair]['bids']
                    s_ask = other_object.data[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                bitfinex_object.data = (bitfinex_object.data, other_object.data, {'m_to_s': m_to_s, 's_to_m': s_to_m})

                return bitfinex_object
            else:
                await asyncio.sleep(max(bitfinex_object.wait_time, other_object.wait_time))
        else:
            return bitfinex_object if bitfinex_object.success is False else other_object


if __name__ == '__main__':
    k = 'MK4XDRHmZJmpP3uD1Uheta6pUcdWW0ShNd3zEhLYVIL'
    s = 'g0hxYy2BComZddkmPUXs5QI5krSbf9pGG4z7GIR5aNB'
    b = BaseBitfinex(key=k, secret=s)

    loop = asyncio.get_event_loop()
    _, available_coin, *_ = b.get_available_coin()
    s, d, m, t = loop.run_until_complete(b.get_deposit_addrs())
    print(d)

    # s, d, m, t = loop.run_until_complete(b.get_balance())
    # s, d, m, t = b.get_available_coin()
    # s, d, m, t = b.sell('xrpbtc', 1)
    # s, d, m, t = b.buy('xrpbtc', 1)
    # s, d, m, t = loop.run_until_complete(b.get_trading_fee())
    # s, d, m, t = loop.run_until_complete(b.get_curr_avg_orderbook(available_coin))
    # s, d, m, t = loop.run_until_complete(b.get_transaction_fee())
    # s, d, m, t = loop.run_until_complete(b.get_deposit_addrs())
