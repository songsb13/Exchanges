import hmac
import math
import hashlib
import requests
import json
import time
import aiohttp
import asyncio
import numpy as np

from urllib.parse import urlencode
from decimal import Decimal, ROUND_DOWN

from base_exchange import BaseExchange


class Binance(BaseExchange):
    def __init__(self, key, secret):
        self._base_url = 'https://api.binance.com'
        self._key = key
        self._secret = secret
        self.exchange_info = None

    def _public_api(self, method, path, extra=None, header=None):
        if extra is None:
            extra = {}

        try:
            rq = requests.get(self._base_url + path, params=extra)
            res = rq.json()

            if 'msg' in res:
                return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['msg'],
                                                                                                path, extra), 1

            else:
                return True, res, '', 1

        except Exception as ex:
            return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra), 1

    def _private_api(self, method, path, extra=None):
        if extra is None:
            extra = {}

        try:
            query = self._sign_generator(extra)
            sig = query.pop('signature')
            query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)
            rq = requests.request(method, self._base_url + path, data=query, headers={"X-MBX-APIKEY": self._key})
            res = rq.json()

            if 'msg' in res:
                return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['msg'],
                                                                                                path, extra), 1

            else:
                return True, res, '', 1

        except Exception as ex:
            return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra), 1

    def _servertime(self):
        return int(time.time() * 1000)

    def _sign_generator(self, *args):
        params, *_ = args
        if params is None:
            params = {}

        params.update({'timestamp': self._servertime()})

        sign = hmac.new(self._secret.encode('utf-8'),
                        urlencode(sorted(params.items())).encode('utf-8'),
                        hashlib.sha256
                        ).hexdigest()

        params.update({'signature': sign})

        return params

    def get_exchange_info(self):
        return self._public_api('GET', '/api/v1/exchangeInfo')

    def _get_exchange_info(self):
        for _ in range(3):
            success, stat, message, time_ = self._public_api('GET', '/api/v1/exchangeInfo')
            if success:
                break
        else:
            return False, stat, message, time_
        
        step_size = {}
        for sym in stat['symbols']:
            symbol = sym['symbol']
            market_coin = symbol[-3:]

            if 'BTC' in market_coin:
                trade_coin = symbol[:-3]
                coin = market_coin + '_' + trade_coin

                step_size.update({
                    coin: sym['filters'][2]['stepSize']
                })

        self.exchange_info = step_size

        return True, step_size, '', 0

    def _get_step_size(self, symbol):
        if symbol == 'BTC_BCH':
            symbol = 'BTC_BCC'

        step_size = Decimal(self.exchange_info[symbol]).normalize()

        return True, step_size, '', 0

    def get_precision(self, pair=None):
        if pair == 'BTC_BCH':
            pair = 'BTC_BCC'

        if pair in self.exchange_info:
            return True, (-8, int(math.log10(float(self.exchange_info[pair])))), '', 0
        else:
            return False, '', '[Binance], ERROR_BODY=[{} 호가 정보가 없습니다.], URL=[get_precision]'.format(pair), 60

    def get_available_coin(self):
        if not self.exchange_info:
            success, data, message, time_ = self._get_exchange_info()

            if not success:
                return False, '', message, time_

        return True, [coin for coin in self.exchange_info.keys()], '', 0

    def buy(self, coin, amount, price=None):
        params = {}
        if price is None:
            params['type'] = 'MARKET'
        else:
            params['type'] = 'LIMIT'

        params.update({
                    'symbol': coin,
                    'side': 'buy',
                    'quantity': '{0:4f}'.format(amount).strip(),
                  })

        return self._private_api('POST', '/api/v3/order', params)

    def sell(self, coin, amount, price=None):
        params = {}
        if price is None:
            params['type'] = 'MARKET'
        else:
            params['type'] = 'LIMIT'

        params.update({
                    'symbol': coin,
                    'side': 'sell',
                    'quantity': '{}'.format(amount),
                  })

        return self._private_api('POST', '/api/v3/order', params)

    def fee_count(self):
        return 1

    def bnc_btm_quantizer(self, symbol):
        binance_qtz = self._get_step_size(symbol)[1]
        return Decimal(10) ** -4 if binance_qtz < Decimal(10) ** -4 else binance_qtz

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        coin = currency_pair.split('_')
        if coin[1] == 'BCH':
            coin[1] = 'BCC'

        suc, data, message, time_ = self.buy(coin[1] + coin[0], alt_amount)

        if not suc:
            return False, data, message, time_

        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[coin[1]])
        alt_amount = alt_amount.quantize(self.bnc_btm_quantizer(currency_pair), rounding=ROUND_DOWN)

        return True, alt_amount, '', 0

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        coin = currency_pair.split('_')
        if coin[1] == 'BCH':
            coin[1] = 'BCC'

        for _ in range(10):
            suc, data, message, time_ = self.sell(coin[1] + coin[0], alt_amount)

            if suc:
                return True, data, '', 0

            else:
                time.sleep(time_)

        else:
            return False, '', message, 1

    def get_ticker(self, market):
        for _ in range(3):
            success, data, message, time_ = self._public_api('GET', '/api/v1/ticker/24hr')
            if success:
                return True, data, '', time

        else:
            return False, '', message, time_

    def withdraw(self, coin, amount, to_address, payment_id=None):
        if coin == 'BCH':
            coin = 'BCC'
        params = {
                    'asset': coin,
                    'address': to_address,
                    'amount': '{}'.format(amount),
                    'name': 'SAICDiffTrader'
                }

        if payment_id:
            tag_dic = {'addressTag': payment_id}
            params.update(tag_dic)

        return self._private_api('POST', '/wapi/v3/withdraw.html', params)

    def get_candle(self, coin, unit, count):
        path = '/'.join([self._base_url, 'api', 'v1', 'klines'])

        params = {
                    'symbol': coin,
                    'interval': '{}m'.format(unit),
                    'limit': count,
        }
        # 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        suc, data, message, time_ = self._public_api('GET', path, params)

        if not suc:
            return suc, data, message, time_

        history = {
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': [],
            'timestamp': [],
        }

        try:
            for info in data:  # 리스트가 늘어날 수도?
                o, h, l, c, vol, ts = list(map(float, info[1:7]))

                history['open'].append(o)
                history['high'].append(h)
                history['low'].append(l)
                history['close'].append(c)
                history['volume'].append(vol)
                history['timestamp'].append(ts)

            return True, history, ''

        except Exception as ex:
            return False, '', 'history를 가져오는 과정에서 에러가 발생했습니다. =[{}]'.format(ex)

    async def _async_private_api(self, method, path, extra=None):
        if extra is None:
            extra = {}

        async with aiohttp.ClientSession(headers={"X-MBX-APIKEY": self._key}) as s:
            query = self._sign_generator(extra)

            try:
                if method == 'GET':
                    sig = query.pop('signature')
                    query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)
                    rq = await s.get(self._base_url + path + "?{}".format(query))

                else:
                    rq = await s.post(self._base_url + path, data=query)

                res = await rq.text()
                res = json.loads(res)

                if 'msg' in res:
                    return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['msg'],
                                                                                                    path, extra), 1

                else:
                    return True, res, '', 0

            except Exception as ex:
                return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex,
                                                                                                path, extra), 1

    async def _async_public_api(self, method, path, extra=None, header=None):
        if extra is None:
            extra = {}

        async with aiohttp.ClientSession() as s:
            rq = await s.get(self._base_url + path, params=extra)

        try:
            res = await rq.text()
            res = json.loads(res)

            if 'msg' in res:
                return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(res['msg'],
                                                                                                path, extra), 1

            else:
                return True, res, '', 0

        except Exception as ex:
            return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex,
                                                                                            path, extra), 1

    async def _get_balance(self):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('GET', '/api/v3/account')
            if success:
                return True, data, message, time_
            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_deposit_addrs(self, symbol):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('GET', '/wapi/v3/depositAddress.html', {'asset': symbol})

            if success:
                return True, data, message, time_
            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_orderbook(self, symbol):
        for _ in range(3):
            success, data, message, time_ = await self._async_public_api('GET', '/api/v1/depth', {'symbol': symbol})
            print(message)
            if success:
                return True, data, message, time_
            time.sleep(time_)

        else:
            return False, '', message, time_

    async def get_deposit_addrs(self, coin_list=None):
        av_suc, coin_list, av_msg, av_time = self.get_available_coin()

        if not av_suc:
            return False, '', av_msg, av_time

        try:
            ret_msg = ""
            rq_dic = {}
            coin_list.append('BTC_BTC')

            for coin in coin_list:
                coin = coin.split('_')[1]
                if coin == 'BCH':
                    coin = 'BCC'

                rq_suc, rq_data, rq_msg, rq_time = await self._get_deposit_addrs(coin)

                if not rq_data['success']:
                    ret_msg += '[{}]해당 코인은 점검 중입니다.\n'.format(coin)
                    continue

                rq_dic[coin] = rq_data['address']

                if 'addressTag' in rq_data:
                    rq_dic[coin + 'TAG'] = rq_data['addressTag']
            return True, rq_dic, ret_msg, 0

        except Exception as ex:
            return False, '', '[BINANCE] ERROR_BODY=[입금 주소를 가져오는데 실패했습니다. {}]'.format(ex), 1

    async def get_avg_price(self,coins):  # 내거래 평균매수가
        # 해당 함수는 현재 미사용 상태
        try:
            amount_price_list, res_value = [], []
            for coin in coins:
                total_price, bid_count, total_amount = 0, 0, 0

                for _ in range(10):
                    hist_suc, history, hist_msg, hist_time = await self._async_public_api(
                        '/api/v3/allOrders', {'symbol': coin})

                    if hist_suc:
                        break

                    else:
                        time.sleep(1)

                else:
                    # history 값을 가져오는데 실패하는 경우.
                    return False, '', '[Binance]History값을 가져오는데 실패했습니다. [{}]'.format(hist_msg), hist_time

                history.reverse()
                for _data in history:
                    side = _data['side']
                    n_price = float(_data['price'])
                    price = Decimal(n_price - (n_price * 0.1)).quantize(Decimal(10) ** -6)
                    amount = Decimal(_data['origQty']).quantize(Decimal(10) ** -6)
                    if side == 'BUY':
                        amount_price_list.append({
                            '_price': price,
                            '_amount': amount
                        })
                        total_price += price
                        total_amount += amount
                        bid_count += 1
                    else:
                        total_amount -= amount
                    if total_amount <= 0:
                        bid_count -= 1
                        total_price = 0
                        amount_price_list.pop(0)

                _values = {coin: {
                    'avg_price': total_price / bid_count,
                    'coin_num': total_amount
                }}
                res_value.append(_values)

            return True, res_value, '', 0

        except Exception as ex:
            return False, '', '[Binance]평균 값을 가져오는데 실패했습니다. [{}]'.format(ex), 1

    async def get_trading_fee(self):
        return True, 0.001, '', 0

    async def get_transaction_fee(self):
        fees = {}
        for _ in range(3):
            try:
                async with aiohttp.ClientSession() as s:
                    try:
                        rq = await s.get('https://www.binance.com/assetWithdraw/getAllAsset.html')
                        data_list = await rq.text()
                        data_list = json.loads(data_list)

                        if not data_list:
                            time.sleep(3)
                            continue
                    except Exception as ex:
                        return False, '', '[BINANCE], ERROR_BODY=[출금 비용을 가져오는데 실패했습니다. {}]'.format(ex), 60

                for f in data_list:
                    if f['assetCode'] == 'BCC':
                        f['assetCode'] = 'BCH'
                    fees[f['assetCode']] = Decimal(f['transactionFee']).quantize(Decimal(10)**-8)

                return True, fees, '', 0

            except Exception as ex:
                return False, '', '[BINANCE], ERROR_BODY=[출금 비용을 가져오는데 실패했습니다. {}]'.format(ex), 60

        else:
            return False, '', '[BINANCE], EEROR_BODY=[출금비용을 가져오는데 실패했습니다. {}],', 60

    async def get_balance(self):
        suc, data, message, time_ = await self._get_balance()

        if not suc:
            return False, '', message, time_

        balance = {}
        for bal in data['balances']:
            if bal['asset'] == 'BCC':
                bal['asset'] = 'BCH'

            if float(bal['free']) > 0:
                balance[bal['asset'].upper()] = float(bal['free'])

        return True, balance, '', 0

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        try:
            avg_order_book = {}
            for currency_pair in coin_list:
                print(currency_pair)
                if currency_pair == 'BTC_BTC':
                    continue

                sp = currency_pair.split('_')
                success, book, message, time_ = await self._get_orderbook(sp[1] + sp[0])

                if not success:
                    return False, '', message, time_

                avg_order_book[currency_pair] = {}
                for type_ in ['asks', 'bids']:
                    order_amount, order_sum = 0, 0

                    for data in book[type_]:
                        order_amount += Decimal(data[1])  # 0 - price 1 - qty
                        order_sum += (Decimal(data[0]) * Decimal(data[1])).quantize(Decimal(10) ** -8)
                        if order_sum >= Decimal(btc_sum):
                            _v = ((order_sum / order_amount).quantize(Decimal(10) ** -8))
                            avg_order_book[currency_pair][type_] = _v
                            break
            return True, avg_order_book, '', 0
        except Exception as ex:
            return False, '', '[BINANCE], ERROR_BODY=[{}], URL=[get_curr_avg_orderbook]'.format(ex), 1

    async def compare_orderbook(self, other, coins, default_btc=1):
        for _ in range(3):
            binance_res, other_res = await asyncio.gather(
                self.get_curr_avg_orderbook(coins, default_btc),
                other.get_curr_avg_orderbook(coins, default_btc)
            )

            binance_suc, binance_avg_orderbook, binance_msg, binance_times = binance_res
            other_suc, other_avg_orderbook, other_msg, other_times = other_res

            if 'BTC' in coins:
                # 나중에 점검
                coins.remove('BTC')

            if binance_suc and other_suc:
                m_to_s = {}
                for currency_pair in coins:
                    m_ask = binance_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in coins:
                    m_bid = binance_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                res = binance_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m}

                return True, res, '', 0

            else:
                time.sleep(binance_times)
                continue

        if not binance_suc or not other_suc:
            return False, '', 'binance_error-[{}] other_error-[{}]'.format(binance_msg, other_msg), binance_times


if __name__ == '__main__':
    k = ''
    s = ''
    b = Binance(k, s)
    s, available, *_ = b.get_available_coin()
    s, d, m, t = b.sell('XRPBTC', 1)
    loop = asyncio.get_event_loop()
    # todo ---Done---
    # s, d, m, t = b.get_available_coin()
    # s, d, m, t = b.buy('XRPBTC', 1)
    # s, d, m, t = b.sell('XRPBTC', 1)
    # s, d, m, t = b.withdraw('XRPBTC', 1, 'test')

    # print(s, d)
    #
    # loop = asyncio.get_event_loop()
    # s, d, m ,t = loop.run_until_complete(b.get_balance())
    # print(d, m)
    # s, d, m, t = loop.run_until_complete(b.get_deposit_addrs())
    # s, d, m, t = loop.run_until_complete(b.get_transaction_fee())
    # s, d, m, t = loop.run_until_complete(b.get_curr_avg_orderbook(available[:5]))
