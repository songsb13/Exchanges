import requests
import time
import jwt
import json
import asyncio
import aiohttp
import numpy as np

from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlencode

from base_exchange import BaseExchange


class BaseUpbit(BaseExchange):
    def __init__(self, key, secret):
        self._base_url = 'https://api.upbit.com/v1'
        self._key = key
        self._secret = secret

    def __repr__(self):
        return 'BaseUpbit'

    def __str__(self):
        return '업비트 기본'

    def _public_api(self, method, path, extra=None, header=None):
        if header is None:
            header = {}

        if extra is None:
            extra = {}

        method = method.upper()
        path = '/'.join([self._base_url, path])
        if method == 'GET':
            rq = requests.get(path, headers=header, params=extra)
        elif method == 'POST':
            rq = requests.post(path, headers=header, data=extra)
        else:
            return False, '', '[{}]incorrect method'.format(method), 1

        try:
            res = rq.json()

            if 'error' in res:
                return False, '', '[UPBIT], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['error']['message'],
                                                                                              path, extra), 1

            else:
                return True, res, '', 0

        except Exception as ex:
            return False, '', '[UPBIT], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra), 1

    def _private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }

        if extra is not None:
            payload.update({'query': urlencode(extra)})

        header = {'Authorization': self._sign_generator(payload)}

        return self._public_api(method, path, extra, header)

    def _sign_generator(self, *args):
        payload, *_ = args
        return 'Bearer {}'.format(jwt.encode(payload, self._secret,).decode('utf8'))

    def fee_count(self):
        # 몇변의 수수료가 산정되는지
        return 1

    def get_ticker(self, market):
        market = market.replace('_', '-')
        for _ in range(3):
            success, data, message, time_ = self._public_api('get', 'ticker', {'markets': market})

            if success:
                return True, data[0], message, time_
            time.sleep(time_)

        else:
            return False, '', message, time_

    def _currencies(self):
        # using get_currencies, service_currencies
        for _ in range(3):
            success, data, message, time_ = self._public_api('get', '/'.join(['market', 'all']))

            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    def get_available_coin(self):
        success, currencies, message, time_ = self._currencies()

        if not success:
            return False, '', message, time_

        else:
            res = []
            [res.append(data['market'].replace('-', '_')) for data in currencies if data['market'].split('-')[1] not in res]
            return True, res, '', 0

    def service_currencies(self, currencies):
        # using deposit_addrs
        res = []
        [res.append(data.split('_')[1]) for data in currencies if data.split('_')[1] not in res]
        return res

    def get_order_history(self, uuid):
        return self._private_api('get', 'order', {'uuid': uuid})

    def withdraw(self, coin, amount, to_address, payment_id=None):
        params = {
                    'currency': coin,
                    'address': to_address,
                    'amount': str(amount),
                }

        if payment_id:
            params.update({'secondary_address': payment_id})

        return self._private_api('post', '/'.join(['withdraws', 'coin']), params)

    def buy(self, coin, amount, price=None):
        params = {}
        if price is None:
            if price is None:
                params['ord_type'] = 'price'
            else:
                params['ord_type'] = 'limit'

        amount, price = map(str, (amount, price * 1.05))
        coin = coin.replace('_', '-')

        params.update({
            'market': coin,
            'side': 'bid',
            'volume': amount,
            'price': price,
        })

        return self._private_api('POST', 'orders', params)

    def sell(self, coin, amount, price=None):
        params = {}
        if price is None:
            if price is None:
                params['ord_type'] = 'market'
            else:
                params['ord_type'] = 'limit'

        amount, price = map(str, (amount, price * 0.95))
        coin = coin.replace('_', '-')

        params.update({
            'market': coin,
            'side': 'ask',
            'volume': amount,
            'price': price,
        })

        return self._private_api('POST', 'orders', params)

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        success, data, msg, time_ = self.buy(currency_pair, btc_amount)
        
        if success:
            alt_amount *= 1 - Decimal(td_fee)
            alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
            alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

            return True, alt_amount, ''
        else:
            return False, '', msg, time_

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        return self.sell(currency_pair, btc_amount)

    def get_precision(self):
        return True, (-8, -8), '', 0

    async def _async_public_api(self, method, path, extra=None, header=None):
        if header is None:
            header = {}

        if extra is None:
            extra = {}
        try:
            async with aiohttp.ClientSession(headers=header) as s:
                method = method.upper()
                path = '/'.join([self._base_url, path])

                if method == 'GET':
                    rq = await s.get(path, headers=header, params=extra)
                elif method == 'POST':
                    rq = await s.post(path, headers=header, data=extra)
                else:
                    return False, '', '[{}]incorrect method'.format(method), 1

                res = json.loads(await rq.text())

                if 'error' in res:
                    return False, '', '[UPBIT], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(
                        res['error']['message'],
                        path, extra), 1

                else:
                    return True, res, '', 0
        except Exception as ex:
            return False, '', '[UPBIT], ERROR_BODY=[{}], URL=[{}, PARAMETER=[{}]]'.format(ex, path, extra), 1

    async def _async_private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }

        if extra is not None:
            payload.update({'query': urlencode(extra)})

        header = {'Authorization': self._sign_generator(payload)}

        return await self._async_public_api(method, path, extra, header)

    async def _get_balance(self):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('get', 'accounts')
            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_orderbook(self, symbol):
        for _ in range(3):
            success, data, message, time_ = await self._async_public_api('get', 'orderbook', {'markets': symbol})
            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_deposit_addrs(self, symbol=None):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('get', '/'.join(['deposits', 'coin_addresses']))
            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_transaction_fee(self, currency):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('get', '/'.join(['withdraws', 'chance']),
                                                                          {'currency': currency})
            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def get_deposit_addrs(self, coin_list=None):
        success, data, message, time_ = await self._get_deposit_addrs()

        if not success:
            return False, '', message, time_

        dic_ = {}
        for d in data:
            dic_[d['currency']] = d['deposit_address']

            if d['secondary_address']:
                dic_[d['currency'] + 'TAG'] = d['secondary_address']

        return True, dic_, message, time_

    async def get_transaction_fee(self):
        suc, currencies, msg, time_ = self.get_available_coin()

        if not suc:
            return False, '', msg, time_

        tradable_currencies = self.service_currencies(currencies)

        fees = {}
        for currency in tradable_currencies:
            ts_suc, ts_data, ts_msg, ts_time = await self._get_transaction_fee(currency)

            if not ts_suc:
                return False, '', msg, ts_time

            else:
                if ts_data['currency']['withdraw_fee'] is None:
                    ts_data['currency']['withdraw_fee'] = 0

                fees[currency] = Decimal(ts_data['currency']['withdraw_fee']).quantize(Decimal(10) ** -8)

            await asyncio.sleep(0.1)

        return True, fees, '', 0

    async def get_balance(self):
        success, data, message, time_ = await self._get_balance()

        if success:
            return True, {bal['currency']: bal['balance'] for bal in data}, '', 0
        else:
            return False, '', message, time_

    async def get_btc_orderbook(self, btc_sum):
        s, d, m, t = await self._get_orderbook('KRW-BTC')

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        # todo 이슈발견: btc_sum에 도달하는? 일치하지 않는 값을 가져오는 경우 어떻게 처리하는가?
        avg_order_book = {}
        for coin in coin_list:
            coin = coin.replace('_', '-')
            suc, book, msg, time_ = await self._get_orderbook(coin)

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

    async def get_trading_fee(self):
        return True, 0.0005, '', 0


class UpbitBTC(BaseUpbit):
    def __init__(self, *args):
        super(UpbitBTC, self).__init__(*args)

    def __repr__(self):
        return 'UpbitBTC'

    def __str__(self):
        return '업비트 BTC마켓'


class UpbitKRW(BaseUpbit):
    def __init__(self, *args):
        super(UpbitKRW, self).__init__(*args)

    def __repr__(self):
        return 'UpbitKRW'

    def __str__(self):
        return '업비트 KRW마켓'

    def fee_count(self):
        return 2

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        for _ in range(3):
            success, data, message, time_ = self.sell('BTC', btc_amount)
            if success:
                break

            else:
                if '부족합니다.' in message:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
        else:
            return False, '', message, time_

        currency_pair = currency_pair.split('_')[1]

        for _ in range(3):
            success, data, message, time_ = self.buy(currency_pair, Decimal(alt_amount))

            if success:
                break

            else:
                if '부족합니다.' in message:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
        else:
            return False, '', message, time_

        alt_amount *= ((1 - Decimal(td_fee)) ** 2)
        alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return True, alt_amount, '', 0

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        currency_pair = currency_pair.split('_')[1]

        for _ in range(10):
            success, data, message, time_ = self.sell(currency_pair, alt_amount)

            if success:
                break

            else:
                if '부족합니다.' in message:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue

        else:
            return False, '', message, time_

        success, data, message, time_ = self.buy('BTC', btc_amount)

        if not success:
            return False, '', message, time_

        return True

    def get_step(self, price):
        if price >= 2000000:
            return 1000
        elif 2000000 > price >= 1000000:
            return 500
        elif 1000000 > price >= 500000:
            return 100
        elif 500000 > price >= 100000:
            return 50
        elif 100000 > price >= 10000:
            return 10
        elif 10000 > price >= 1000:
            return 5
        elif price < 10:
            return 0.01
        elif price < 100:
            return 0.1
        elif price < 1000:
            return 1

    def buy(self, coin, amount, price=None):
        params = {}
        if price is None:
            params['ord_type'] = 'price'
        else:
            params['ord_type'] = 'limit'

        coin = 'KRW-{}'.format(coin.split('_')[1])
        price = int(price)

        params.update({
            'market': coin,
            'side': 'bid',
            'volume': str(amount),
            'price': (price * 1.05) + (self.get_step(price * 1.05) - ((price * 1.05) % self.get_step(price * 1.05))),
        })

        return self._private_api('POST', 'orders', params)

    def sell(self, coin, amount, price=None):
        params = {}
        if price is None:
            params['ord_type'] = 'market'
        else:
            params['ord_type'] = 'limit'

        coin = 'KRW-{}'.format(coin.split('_')[1])
        price = int(price)

        params.update({
            'market': coin,
            'side': 'ask',
            'volume': str(amount),
            'price': (price * 0.95) - ((price * 0.95) % self.get_step(price * 0.95)),
        })

        return self._private_api('POST', 'orders', params)


class UpbitUSDT(UpbitKRW):
    def __init__(self, *args):
        super(UpbitUSDT, self).__init__(*args)

    def __repr__(self):
        return 'UpbitUSDT'

    def __str__(self):
        return '업비트 USDT마켓'

    def buy(self, coin, amount, price=None):
        params = {}
        if price is None:
            params['ord_type'] = 'price'
        else:
            params['ord_type'] = 'limit'

        coin = 'USDT-{}'.format(coin.split('_')[1])
        price = int(price)

        params.update({
            'market': coin,
            'side': 'bid',
            'volume': str(amount),
            'price': (price * 1.05) + (self.get_step(price * 1.05) - ((price * 1.05) % self.get_step(price * 1.05))),
        })

        return self._private_api('POST', 'orders', params)

    def sell(self, coin, amount, price=None):
        params = {}
        if price is None:
            params['ord_type'] = 'market'
        else:
            params['ord_type'] = 'limit'

        coin = 'USDT-{}'.format(coin.split('_')[1])

        price = int(price)

        params.update({
            'market': coin,
            'side': 'ask',
            'volume': str(amount),
            'price': (price * 0.95) - ((price * 0.95) % self.get_step(price * 0.95)),
        })

        return self._private_api('POST', 'orders', params)


if __name__ == '__main__':
    key = ''
    secret = ''

    u = UpbitKRW(key, secret)

    _, get_available_coin, *_ = u.get_available_coin()

    loop = asyncio.get_event_loop()

    # todo UpbitBTC -----done-----
    # _, get_available_coin, *_ = u.get_available_coin()
    #
    # for coin in get_available_coin:
    #     print(coin)
    #
    # service_currencies = u.service_currencies(get_available_coin)
    #
    # for svc in service_currencies:
    #     print(svc)
    #
    # _, ticker, *_ = u.get_ticker('BTC_XRP')
    #
    # print(ticker)

    # loop = asyncio.get_event_loop()
    # _, balance, *_ = loop.run_until_complete(u.get_balance())
    #
    # print(balance)
    #
    # _, fee, *_ = loop.run_until_complete(u.get_transaction_fee())
    #
    # print(fee)
    #
    # _, orderbook, *_ = loop.run_until_complete(u.get_curr_avg_orderbook(get_available_coin))
    #
    # print(orderbook)

    # s, dp_set, msg, time_ = loop.run_until_complete(u.get_deposit_addrs(get_available_coin))

    # print(dp_set)
    #
    # s, d, m, t = u.buy('BTC-ADA', 1)
    #
    # s, d, m, t = u.sell('BTC-ADA', 1)
