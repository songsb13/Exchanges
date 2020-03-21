import json
import base64
import hmac
import hashlib
import requests
import time
import aiohttp
import asyncio
from decimal import Decimal, ROUND_DOWN

from base_exchange import BaseExchange, ExchangeResult


class Bitfinex(BaseExchange):
    def __init__(self, *args, **kwargs):
        '''
        :param key: input your upbit key
        :param secret: input your upbit secret
        '''
        self._base_url = 'https://api.bitfinex.com'

        if kwargs:
            self._key = kwargs['key']
            self._secret = kwargs['secret']

        self._symbol_full_name = {}

        ExchangeResult.set_exchange_name = 'Bitfinex'

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
            res_object = self._public_api('GET', '/v2/conf/pub:map:currency:label')

            if res_object.success is False:
                time.sleep(res_object.wait_time)
                continue
            dic = {each[0]: each[1] for each in res_object.data[0]}

            res_object.data = self._symbol_full_name = dic

        return res_object

    def _public_api(self, method, path, extra=None, header=None):
        debugger.debug('[Bitfinex]Parameters=[{}, {}, {}, {}], function name=[_public_api]'.format(method, path, extra, header))

        try:
            if extra is None:
                extra = dict()

            path = self._base_url + path
            rq = requests.get(path, params=extra)
            response = rq.json()

            if 'message' in response:
                error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['message'], path, extra)
            elif 'error' in response:
                error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['error'], path, extra)
            else:
                error_message = None

        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult(*result)

    def _private_api(self, method, path, extra=None):
        debugger.debug('[Bitfinex]Parameters=[{}, {}, {}], function name=[_private_api]'.format(method, path, extra))

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
                error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['message'], path, extra)
            elif 'error' in response:
                error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['error'], path, extra)
            else:
                error_message = None
        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult(*result)

    def _currencies(self):
        for _ in range(3):
            res_object = self._public_api('GET', '/v1/symbols')

            if res_object.success:
                break
            time.sleep(res_object.wait_time)

        return res_object

    def get_precision(self, pair=None):
        return True, (-8, -8), '', 0

    def get_ticker(self, market):
        for _ in range(3):
            bitfinex_currency_pair = ''.join(market.split('_')[::-1]).lower()
            res_object = self._public_api('GET', 'pubticker', {'pair': bitfinex_currency_pair})

            if res_object.success:
                res_object.data = float(res_object.data['last_price'])
                break

    def buy(self, market, quantity, price=None):
        debugger.debug('[Bitfinex]Parameters=[{}, {}, {}], function name=[buy]'.format(market, quantity, price))

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

        return self._private_api('POST', '/v1/order/new', params)

    def sell(self, market, quantity, price=None):
        debugger.debug('[Bitfinex]Parameters=[{}, {}, {}], function name=[sell]'.format(market, quantity, price))

        amount, price = [str(Decimal(data).quantize(Decimal(10) ** -8)) for data in [quantity, price]]
        market_type = 'market' if price is None else 'limit'

        params = {
            'symbol': market,
            'amount': amount,
            'side': 'sell',
            'type': market_type,
            'price': price
        }

        return self._private_api('POST', '/v1/order/new', params)

    def withdraw(self, coin, amount, to_address, payment_id=None):
        debugger.debug('[Bitfinex]Parameters=[{}, {}, {}, {}], function name=[sell]'.format(coin, amount,
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

        return self._private_api('POST', '/v1/withdraw', params)

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
        base_market, coin = currency.split('_')
        symbol = coin + base_market
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

    async def _async_public_api(self, method, path, extra=None, header=None):
        debugger.debug('[Bitfinex]Parameters=[{}, {}, {}, {}], function name=[_async_public_api]'.format(method, path, extra, header))

        if extra is None:
            extra = dict()

        try:
            url = self._base_url + path
            async with aiohttp.ClientSession() as sync:
                rq = await sync.get(url, params=extra)
                response = json.loads(await rq.text())

                if 'message' in response:
                    error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['message'], path, extra)
                elif 'error' in response:
                    error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['error'], path, extra)
                else:
                    error_message = None
        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult(*result)

    async def _async_private_api(self, method, path, extra=None):
        debugger.debug('[Bitfinex]Parameters=[{}, {}, {}], function name=[_async_private_api]'.format(method, path, extra))

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
                    error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['message'], path, extra)
                elif 'error' in response:
                    error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['error'], path, extra)
                else:
                    error_message = None
        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult(*result)

    async def _get_balance(self):
        for _ in range(3):
            result_object = await self._async_private_api('POST', '/v1/balances')

            if result_object.success:
                break

            time.sleep(result_object.wait_time)

        return result_object

    async def _get_orderbook(self, coin):
        for _ in range(3):
            result_object = await self._async_public_api('GET', '/v1/book/{}'.format(coin))

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
        return await self._async_private_api('POST', '/v1/deposit/new', params)

    async def _get_trading_fee(self, symbol):
        for _ in range(3):
            success, val, msg, st = await self._async_private_api('POST', '/v1/account_infos')

            if success:
                return True, val, msg, st
            time.sleep(st)

        else:
            return False, val, msg, st

    async def _get_transaction_fee(self, symbol):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('POST', '/v1/account_fees')

            if success:
                return True, data, message, time_

            time.sleep(time_)
        else:
            return False, '', message, time_

    async def get_balance(self):
        success, balance_data, message, time_ = await self._get_balance()

        if not success:
            return False, '', message, time_

        elif not balance_data:
            # 밸런스가 없는경우
            return False, '', '[BITFINEX], ERROR_BODY=[Do not have available balance.], URL=[/v1/balances]', 1

        return True, {value['currency'].lower(): float(value['amount']) for value in balance_data if value['type']
                      == 'exchange'}, '', 0

    async def get_deposit_addrs(self, coin_list=None):
        # wallet name이 지정되어 있어야 한다.
        if not self._symbol_full_name:
            success, _, message, time_ = self._get_symbol_full_name()
            if not success:
                return False, '', message, time_

        ac_success, currencies, ac_message, ac_time_ = self.get_available_coin()

        if not ac_success:
            return False, '', ac_message, ac_time_

        coins = {}
        for currency in currencies:
            time.sleep(0.05)
            currency = currency.split('_')[1]

            if currency in ['QTUM', 'DASH', 'IOTA']:
                currency = self._symbol_localizing(currency)

            if currency not in self._symbol_full_name:
                continue

            success, dp_data, message, time_ = await self._get_deposit_addrs(self._symbol_full_name[currency].lower())
            if not success:
                if 'Unknown method' in message:
                    # 상의? 지원하지 않는 코인의 수량이 너무 많음.
                    print(message)
                    continue

                return False, '', message, time_

            upper_currency = currency.upper()

            if 'XRP' == currency or 'XMR' == currency:
                coins['{}TAG'.format(upper_currency)] = dp_data['address']
                coins[upper_currency] = dp_data['address_pool']

            else:
                coins[upper_currency] = dp_data['address']

        return True, coins, '', 0

    async def get_orderbook_latest_version(self, coin):
        # For Trading: if AMOUNT > 0 then bid else ask.
        return await self._async_public_api('GET', '/v2/book/t{}/P0'.format(coin.upper()))

    async def get_trading_fee(self):
        success, val, msg, st = await self._get_trading_fee(symbol=None)
        # self.last_retrieve_time = time.time()
        if not success:
            return False, '', msg, st
        elif not val:
            return False, '', '[BITFINEX] ERROR_BODY=[Data is not exist]', 1

        ret = float(val[0]['taker_fees'])/100.0

        return True, ret, '', 0

    async def get_transaction_fee(self):
        success, data, message, time_ = await self._get_transaction_fee(symbol=None)

        if not success:
            return False, '', message, time_

        else:
            dic_ = {}
            data = data['withdraw']
            for key_ in data:
                if key_ in ['QTM', 'DSH', 'IOT']:
                    processing_key = self._symbol_customizing(key_.lower()).upper()
                else:
                    processing_key = key_

                dic_[processing_key] = float(data[key_])

            return True, dic_, '', time_

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        avg_orderbook = {}
        for pair in coin_list:
            base_market, coin = pair.split('_')

            if coin in ['QTUM', 'DASH', 'IOTA']:
                coin = self._symbol_localizing(coin)

            symbol = (coin + base_market).lower()
            ob_success, orderbook, ob_message, ob_time = await self._get_orderbook(symbol)
            if not ob_success:
                return False, '', ob_message, ob_time

            avg_orderbook[pair] = {}
            for order_type in ['asks', 'bids']:
                sum = Decimal(0.0)
                total_coin_num = Decimal(0.0)
                for data in orderbook[order_type]:
                    price = data['price']
                    alt_coin_num = data['amount']
                    sum += Decimal(price) * Decimal(alt_coin_num)
                    total_coin_num += Decimal(alt_coin_num)
                    if sum > btc_sum:
                        break
                avg_orderbook[pair][order_type] = (sum/total_coin_num).quantize(Decimal(10) ** -8)

        return True, avg_orderbook, '', 0

    async def compare_orderbook(self, other, coins=None, default_btc=1):
        if coins is None:
            coins = []

        currency_pairs = coins
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            bitfinex_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs,
                                                                                              default_btc),
                                                                  other.get_curr_avg_orderbook(currency_pairs,
                                                                                               default_btc))
            success, bitfinex_avg_orderbook, err, st = bitfinex_result
            success2, other_avg_orderbook, err2, st2 = other_result
            if success and success2:
                m_to_s = {}
                for currency_pair in currency_pairs:
                    m_ask = bitfinex_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in currency_pairs:
                    m_bid = bitfinex_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                ret = (bitfinex_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m})

                return True, ret, '', 0
            else:
                future = asyncio.sleep(st) if st > st2 else asyncio.sleep(st2)
                await future
                continue
        else:
            if not err:
                return False, '', err2, st2
            else:
                return False, '', err, st


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
