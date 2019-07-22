import json
import base64
import hmac
import hashlib
import requests
import time
import aiohttp
import asyncio
from decimal import Decimal, ROUND_DOWN

from base_exchange import BaseExchange


class BaseBitfinex(BaseExchange):
    def __init__(self, **kwargs):
        '''
        :param key: input your upbit key
        :param secret: input your upbit secret
        '''
        self._base_url = 'https://api.bitfinex.com'

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

        if symbol == 'qtm':
            return 'qtum'

        elif symbol == 'iot':
            return 'iota'

        elif symbol == 'dsh':
            return 'dash'

    def _symbol_localizing(self, symbol):
        # change customized symbol to local use symbol

        if symbol == 'QTUM':
            return 'QTM'

        elif symbol == 'IOTA':
            return 'IOT'

        elif symbol == 'DASH':
            return 'DSH'

    def _get_symbol_full_name(self):
        for _ in range(3):
            success, data, message, time_ = self._public_api('GET', '/v2/conf/pub:map:currency:label')

            if not success:
                time.sleep(time_)
                continue

            for loop_ in data[0]:
                self._symbol_full_name[loop_[0]] = loop_[1]

            return True, self._symbol_full_name, '', 0
        else:
            return False, '', message, time_

    def _public_api(self, method, path, extra=None, header=None):
        try:
            if extra is None:
                extra = {}
            path = self._base_url + path
            rq = requests.get(path, params=extra)
            res = rq.json()

            if 'message' in res:
                return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['message'], path,
                                                                                                 extra), 1

            elif 'error' in res:
                return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['error'],
                                                                                                 path,
                                                                                                 extra), 1

            return True, res, '', 0
        except Exception as ex:
            return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path,
                                                                                             extra), 1

    def _private_api(self, method, path, extra=None):
        try:
            if extra is None:
                extra = {}
            url = self._base_url + path

            extra['request'] = path
            extra['nonce'] = str(time.time())

            sign_ = self._sign_generator(extra)

            rq = requests.post(url, json=extra, headers=sign_)

            res = rq.json()

            if 'message' in res:
                return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['message'], path,
                                                                                                 extra), 1

            elif 'error' in res:
                return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['error'],
                                                                                                 path,
                                                                                                 extra), 1

            return True, res, '', 0
        except Exception as ex:
            return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path,
                                                                                             extra), 1

    def _currencies(self):
        for _ in range(3):
            success, data, message, time_ = self._public_api('GET', '/v1/symbols')

            if success:
                return True, data, message, time_
            time.sleep(time_)
        else:
            return False, '', message, time_

    def get_precision(self, pair=None):
        return True, (-8, -8), '', 0

    def get_ticker(self, market):
        for _ in range(3):
            bitfinex_currency_pair = (market.split('_')[-1] + market.split('_')[0]).lower()
            success, price, message, time_ = self._public_api('GET', 'pubticker', {'pair': bitfinex_currency_pair})
            if not success:
                continue

            current_price = float(price['last_price'])

            return True, current_price, "", 0
        else:
            return False, '', message, time_

    def buy(self, market, quantity, price=None):
        params = {
            'symbol': market,
            'amount': str(Decimal(quantity).quantize(Decimal(10) ** -8)),
            'side': 'buy'
        }

        if price:
            params['type'] = 'limit'
            params['price'] = str(Decimal(price).quantize(Decimal(10) ** -8))
        else:
            params['type'] = 'market'
            params['price'] = str(Decimal(1).quantize(Decimal(10) ** -8))

        return self._private_api('POST', '/v1/order/new', params)

    def sell(self, market, quantity, price=None):
        params = {
            'symbol': market,
            'amount': str(Decimal(quantity).quantize(Decimal(10) ** -8)),
            'side': 'buy'
        }

        if price:
            params['type'] = 'limit'
            params['price'] = str(Decimal(price).quantize(Decimal(10) ** -8))
        else:
            params['type'] = 'market'
            params['price'] = str(Decimal(1).quantize(Decimal(10) ** -8))

        return self._private_api('POST', '/v1/order/new', params)

    def withdraw(self, coin, amount, to_address, payment_id=None):
        if not self._symbol_full_name:
            # 로직 상 deposit_addrs에서 값이 지정됨.
            success, _, message, time_ = self._get_symbol_full_name()
            return False, '', message, time_

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
        success, coin_list, message, time_ = self._currencies()

        if not success:
            return False, '', message, time_
        available_list = []

        for coin in coin_list:
            if 'btc' in coin[3:]:
                if coin[:-3] in ['qtm', 'dsh', 'iot']:
                    alt = self._symbol_customizing(coin[:-3])
                else:
                    alt = coin[:-3]

                available_list.append('BTC_{}'.format(alt.upper()))
        return True, available_list, '', 0

    def base_to_alt(self, currency, tradable_btc, alt_amount, td_fee, tx_fee):
        coin = currency.split('_')
        symbol = coin[1] + coin[0]
        success, val, message, time_ = self.buy(symbol.lower(), alt_amount)
        if not success:
            return False, '', message, time_

        alt = alt_amount
        alt *= ((1 - Decimal(td_fee)) ** 1)
        alt -= Decimal(tx_fee[coin[1]])
        alt = alt.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return True, alt, '', 0

    def alt_to_base(self, currency, tradable_btc, alt_amount):
        coin = currency.split('_')
        symbol = coin[1] + coin[0]
        return self.sell(symbol.lower(), alt_amount)

        # for _ in range(10):
        #     success, val, message, time_ = self.sell(currency, alt_amount)
        #     if success:
        #         return True, '', '', 0
        #     else:
        #         time.sleep(time_)
        # else:
        #     return False, '', message, time_

    async def _async_public_api(self, method, path, extra=None, header=None):
        if extra is None:
            extra = {}

        try:
            url = self._base_url + path
            async with aiohttp.ClientSession() as sync:
                rq = await sync.get(url, params=extra)
                res = json.loads(await rq.text())

                if 'message' in res:
                    return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['message'],
                                                                                                     path,
                                                                                                     extra), 1

                elif 'error' in res:
                    return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['error'],
                                                                                                     path,
                                                                                                     extra), 1

                return True, res, '', 0

        except Exception as ex:
            return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path,
                                                                                             extra), 1

    async def _async_private_api(self, method, path, extra=None):
        if extra is None:
            extra = {}

        try:
            url = self._base_url + path
            async with aiohttp.ClientSession() as sync:
                extra['request'] = path
                extra['nonce'] = str(time.time())

                sign_ = self._sign_generator(extra)

                rq = await sync.post(url, data=extra, headers=sign_)

                res = json.loads(await rq.text())

                if 'message' in res:
                    return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['message'],
                                                                                                     path,
                                                                                                     extra), 1
                elif 'error' in res:
                    return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['error'],
                                                                                                     path,
                                                                                                     extra), 1
                return True, res, '', 0
        except Exception as ex:
            return False, '', '[BITFINEX], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path,
                                                                                             extra), 1

    async def _get_balance(self):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('POST', '/v1/balances')

            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_orderbook(self, coin):
        for _ in range(3):
            success, data, message, time_ = await self._async_public_api('GET', '/v1/book/{}'.format(coin))

            if success:
                return True, data, message, time_
            time.sleep(time_)

        else:
            return False, data, message, time_

    async def _get_deposit_addrs(self, currency):
        # wallet name이 지정되어 있어야 한다.
        if not self._symbol_full_name:
            success, _, message, time_ = self._get_symbol_full_name()
            if not success:
                return False, '', message, time_

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
                    processing_key = self._symbol_customizing(key_)
                else:
                    processing_key = key_

                dic_[processing_key] = float(data[key_])

            return True, dic_, '', time_

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        avg_orderbook = {}
        for pair in coin_list:
            pair_splits = pair.split('_')

            if pair_splits[1] in ['QTUM', 'DASH', 'IOTA']:
                pair_splits[1] = self._symbol_localizing(pair_splits[1])

            symbol = (pair_splits[1] + pair_splits[0]).lower()
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
    s, d, m, t = loop.run_until_complete(b.get_curr_avg_orderbook(available_coin[10:]))
    print(d)

    # s, d, m, t = loop.run_until_complete(b.get_balance())
    # s, d, m, t = b.get_available_coin()
    # s, d, m, t = b.sell('xrpbtc', 1)
    # s, d, m, t = b.buy('xrpbtc', 1)
    # s, d, m, t = loop.run_until_complete(b.get_trading_fee())
    # s, d, m, t = loop.run_until_complete(b.get_curr_avg_orderbook(available_coin))
    # s, d, m, t = loop.run_until_complete(b.get_transaction_fee())
    # s, d, m, t = loop.run_until_complete(b.get_deposit_addrs())
