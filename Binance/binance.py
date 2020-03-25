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

from base_exchange import BaseExchange, ExchangeResult


class Binance(BaseExchange):
    def __init__(self, key, secret):
        self._base_url = 'https://api.binance.com'
        self._key = key
        self._secret = secret
        self.exchange_info = None
        self._get_exchange_info()

        ExchangeResult.set_exchange_name = 'Binance'

    def _public_api(self, method, path, extra=None, header=None):
        debugger.debug('Parameters=[{}, {}, {}, {}], function name=[_public_api]'.format(method, path, extra, header))

        if extra is None:
            extra = dict()

        try:
            rq = requests.get(self._base_url + path, params=extra)
            response = rq.json()

            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['msg'], path, extra) if 'msg' \
                in response else None

        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult(*result)

    def _private_api(self, method, path, extra=None):
        debugger.debug('Parameters=[{}, {}, {}], function name=[_private_api]'.format(method, path, extra))

        if extra is None:
            extra = dict()

        try:
            query = self._sign_generator(extra)
            sig = query.pop('signature')
            query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)
            rq = requests.request(method, self._base_url + path, data=query, headers={"X-MBX-APIKEY": self._key})
            response = rq.json()

            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['msg'], path, extra) if 'msg' \
                in response else None

        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult(*result)

    def _symbol_localizing(self, symbol):
        actual_symbol = dict(
            BCH='BCC'
        )
        return actual_symbol.get(symbol)

    def _symbol_customizing(self, symobl):
        actual_symbol = dict(
            BCC='BCH'
        )

        return actual_symbol.get(symobl)

    def _sign_generator(self, *args):
        params, *_ = args
        if params is None:
            params = dict()

        params.update({'timestamp': int(time.time() * 1000)})

        sign = hmac.new(self._secret.encode('utf-8'),
                        urlencode(sorted(params.items())).encode('utf-8'),
                        hashlib.sha256
                        ).hexdigest()

        params.update({'signature': sign})

        return params

    def _get_exchange_info(self):
        for _ in range(3):
            result_object = self._public_api('GET', '/api/v1/exchangeInfo')
            if result_object.success:
                break

            time.sleep(result_object.wait_time)
        else:
            return result_object

        step_size = dict()
        for sym in result_object.data['symbols']:
            symbol = sym['symbol']
            market_coin = symbol[-3:]

            if 'BTC' in market_coin:
                trade_coin = symbol[:-3]
                coin = market_coin + '_' + trade_coin

                step_size.update({
                    coin: sym['filters'][2]['stepSize']
                })

        self.exchange_info = step_size
        result_object.data = self.exchange_info

        return result_object

    def _get_step_size(self, symbol):
        symbol = self._symbol_localizing(symbol)

        step_size = Decimal(self.exchange_info[symbol]).normalize()

        return True, step_size, '', 0

    def get_precision(self, pair=None):
        pair = self._symbol_localizing(pair)

        if pair in self.exchange_info:
            return True, (-8, int(math.log10(float(self.exchange_info[pair])))), '', 0
        else:
            return False, '', '[Binance], ERROR_BODY=[{} 호가 정보가 없습니다.], URL=[get_precision]'.format(pair), 60

    def get_available_coin(self):
        return True, list(self.exchange_info.keys()), '', 0

    def buy(self, coin, amount, price=None):
        debugger.debug('Parameters=[{}, {}, {}], function name=[buy]'.format(coin, amount, price))

        params = dict()

        params['type'] = 'MARKET' if price is None else 'LIMIT'

        params.update({
                    'symbol': coin,
                    'side': 'buy',
                    'quantity': '{0:4f}'.format(amount).strip(),
                  })

        return self._private_api('POST', '/api/v3/order', params)

    def sell(self, coin, amount, price=None):
        debugger.debug('Parameters=[{}, {}, {}], function name=[sell]'.format(coin, amount, price))

        params = dict()

        params['type'] = 'MARKET' if price is None else 'LIMIT'

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
        debugger.debug('Parameters=[{}, {}, {}, {}], function name=[base_to_alt]'.format(
            currency_pair, btc_amount, alt_amount, td_fee, tx_fee
        ))
        currency_pair = self._symbol_localizing(currency_pair)
        base_market, coin = currency_pair.split('_')

        result_object = self.buy(coin + base_market, alt_amount)

        if result_object.success:
            alt_amount *= 1 - Decimal(td_fee)
            alt_amount -= Decimal(tx_fee[coin])
            alt_amount = alt_amount.quantize(self.bnc_btm_quantizer(currency_pair), rounding=ROUND_DOWN)

            result_object.data = alt_amount

        return result_object

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        debugger.debug('Parameters=[{}, {}, {}], function name=[alt_to_base]'.format(
            currency_pair, btc_amount, alt_amount
        ))
        currency_pair = self._symbol_localizing(currency_pair)
        base_market, coin = currency_pair.split('_')

        for _ in range(10):
            result_object = self.sell(coin + base_market, alt_amount)

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    def get_ticker(self, market):
        for _ in range(3):
            result_object = self._public_api('GET', '/api/v1/ticker/24hr')
            if result_object.success:
                break
        time.sleep(result_object.wait_time)

        return result_object

    def withdraw(self, coin, amount, to_address, payment_id=None):
        debugger.debug('Parameters=[{}, {}, {}, {}], function name=[withdraw]'.format(coin, amount,
                                                                                      to_address, payment_id))

        coin = self._symbol_localizing(coin)
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
        suc, data, message, delay = self._public_api('GET', path, params)

        if not suc:
            return suc, data, message, delay

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
        debugger.debug('Parameters=[{}, {}, {}], function name=[_async_private_api]'.format(method, path, extra))

        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession(headers={"X-MBX-APIKEY": self._key}) as session:
            query = self._sign_generator(extra)

            try:
                if method == 'GET':
                    sig = query.pop('signature')
                    query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)
                    rq = await session.get(self._base_url + path + "?{}".format(query))

                else:
                    rq = await session.post(self._base_url + path, data=query)

                response = json.loads(await rq.text())

                error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['msg'], path, extra) \
                    if 'msg' in response else None

            except Exception as ex:
                error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult(*result)

    async def _async_public_api(self, method, path, extra=None, header=None):
        debugger.debug('Parameters=[{}, {}, {}, {}], function name=[_async_public_api]'.format(method, path, extra, header))

        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession() as session:
            rq = await session.get(self._base_url + path, params=extra)

        try:
            response = json.loads(await rq.text())

            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['msg'], path, extra) \
                if 'msg' in response else None

        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult(*result)

    async def _get_balance(self):
        for _ in range(3):
            result_object = await self._async_private_api('GET', '/api/v3/account')
            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def _get_deposit_addrs(self, symbol):
        for _ in range(3):
            result_object = await self._async_private_api('GET', '/wapi/v3/depositAddress.html', {'asset': symbol})

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def _get_orderbook(self, symbol):
        for _ in range(3):
            result_object = await self._async_public_api('GET', '/api/v1/depth', {'symbol': symbol})
            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def get_deposit_addrs(self, coin_list=None):
        coin_list = list(self.exchange_info.keys())
        try:
            result_message = str()
            return_deposit_dict = dict()
            coin_list.append('BTC_BTC')

            for symbol in coin_list:
                base_, coin = symbol.split('_')
                coin = self._symbol_customizing(coin)

                get_deposit_result_object = await self._get_deposit_addrs(coin)

                if get_deposit_result_object.data['success'] is False:
                    result_message += '[{}]해당 코인은 점검 중입니다.\n'.format(coin)
                    continue

                return_deposit_dict[coin] = get_deposit_result_object.data['address']

                if 'addressTag' in get_deposit_result_object.data:
                    return_deposit_dict[coin + 'TAG'] = get_deposit_result_object.data['addressTag']
            result = (True, return_deposit_dict, result_message, 0)

        except Exception as ex:
            result_message = 'ERROR_BODY=[입금 주소를 가져오는데 실패했습니다. {}]'.format(ex)
            result = (False, '', result_message, 1)

        return ExchangeResult(*result)

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
        suc, data, message, delay = await self._get_balance()

        if not suc:
            return False, '', message, delay

        balance = {}
        for bal in data['balances']:
            if bal['asset'] == 'BCC':
                bal['asset'] = 'BCH'

            if float(bal['free']) > 0:
                balance[bal['asset'].upper()] = Decimal(bal['free']).quantize(Decimal(10)**-8)

        return True, balance, '', 0

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        try:
            avg_order_book = {}
            for currency_pair in coin_list:
                if currency_pair == 'BTC_BTC':
                    continue

                sp = currency_pair.split('_')
                success, book, message, delay = await self._get_orderbook(sp[1] + sp[0])

                if not success:
                    return False, '', message, delay

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
