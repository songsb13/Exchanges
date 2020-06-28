import hmac
import math
import hashlib
import requests
import json
import time
import aiohttp
import asyncio
import numpy as np
import logging
import datetime
import threading

from urllib.parse import urlencode
from copy import deepcopy
from decimal import Decimal, ROUND_DOWN

from Exchanges.base_exchange import BaseExchange, ExchangeResult, DataStore
from Exchanges.Binance.subscriber import BinanceSubscriber
from Util.pyinstaller_patch import *


class Binance(BaseExchange):
    def __init__(self, key, secret, coin_list, time_):
        self.name = 'Binance'
        self._base_url = 'https://api.binance.com'
        self._key = key
        self._secret = secret
        
        self._coin_list = coin_list
        self._candle_time = time_
        
        self.exchange_info = None
        self._get_exchange_info()
        self.data_store = DataStore()
        
        self._lock_dic = dict(orderbook=threading.Lock(), candle=threading.Lock())
        
        self._subscriber = BinanceSubscriber(self.data_store, self._lock_dic)
        
        self._websocket_candle_settings()
        self._websocket_orderbook_settings()
    
    def _websocket_candle_settings(self):
        time_str = '{}m'.format(self._candle_time) if self._candle_time < 60 else '{}h'.format(self._candle_time // 60)
        if not self._subscriber.candle_symbol_set:
            pairs = [(self._symbol_localizing(pair.split('_')[1]) + pair.split('_')[0]).lower()
                     for pair in self._coin_list]
            setattr(self._subscriber, 'candle_symbol_set', pairs)

        if self._subscriber.candle_receiver is None or not self._subscriber.candle_receiver.isAlive():
            self._subscriber.subscribe_candle(time_str)
    
    def _websocket_orderbook_settings(self):
        pairs = [(self._symbol_localizing(pair.split('_')[1]) + pair.split('_')[0]).lower()
                 for pair in self._coin_list]
        if not self._subscriber.orderbook_symbol_set:
            setattr(self._subscriber, 'orderbook_symbol_set', pairs)
    
        if self._subscriber.orderbook_receiver is None or not self._subscriber.orderbook_receiver.isAlive():
            self._subscriber.subscribe_orderbook()

    def _public_api(self, path, extra=None):
        debugger.debug('{}::: Parameters=[{}, {}], function name=[_public_api]'.format(self.name, path, extra))
        if extra is None:
            extra = dict()

        try:
            rq = requests.get(self._base_url + path, params=extra)
            response = rq.json()

            if 'msg' in response:
                msg = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['msg'], path, extra)
                debugger.debug(msg)
                return ExchangeResult(False, '', msg, 1)
            else:
                return ExchangeResult(True, response, '', 0)

        except Exception as ex:
            msg = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, ex, path, extra)
            debugger.debug(msg)
            return ExchangeResult(False, '', msg, 1)

    def _private_api(self, method, path, extra=None):
        debugger.debug('{}::: Parameters=[{}, {}], function name=[_private_api]'.format(self.name, path, extra))

        if extra is None:
            extra = dict()

        try:
            query = self._sign_generator(extra)
            sig = query.pop('signature')
            query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)

            if method == 'GET':
                rq = requests.get(self._base_url + path, params=query, headers={"X-MBX-APIKEY": self._key})
            else:
                rq = requests.post(self._base_url + path, data=query, headers={"X-MBX-APIKEY": self._key})
            response = rq.json()

            if 'msg' in response:
                msg = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(response['msg'], path, extra)
                debugger.debug(msg)
                return ExchangeResult(False, '', msg, 1)
            else:
                return ExchangeResult(True, response, '', 0)

        except Exception as ex:
            msg = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, ex, path, extra)
            debugger.debug(msg)
            return ExchangeResult(False, '', msg, 1)

    def _symbol_localizing(self, symbol):
        actual_symbol = dict(
            BCH='BCC'
        )
        return actual_symbol.get(symbol, symbol)

    def _symbol_customizing(self, symbol):
        actual_symbol = dict(
            BCC='BCH'
        )

        return actual_symbol.get(symbol, symbol)

    def _sai_symbol_converter(self, symbol):
        # BTC_XRP -> XRPBTC
        return ''.join(symbol.split('_')[::-1])

    def _get_server_time(self):
        return self._public_api('/api/v3/time')

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
            result_object = self._public_api('/api/v3/exchangeInfo')
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

        return ExchangeResult(True, step_size, '', 0)

    def get_precision(self, pair=None):
        pair = self._symbol_localizing(pair)

        if pair in self.exchange_info:
            return ExchangeResult(True, (-8, int(math.log10(float(self.exchange_info[pair])))), '', 0)
        else:
            return ExchangeResult(False, '', '{}::: ERROR_BODY=[{} 호가 정보가 없습니다.], URL=[get_precision]'.format(self.name, pair), 60)

    def get_available_coin(self):
        return ExchangeResult(True, list(self.exchange_info.keys()), '', 0)

    def buy(self, coin, amount, price=None):
        debugger.debug('{}::: Parameters=[{}, {}, {}], function name=[buy]'.format(self.name, coin, amount, price))

        params = dict()

        params['type'] = 'MARKET' if price is None else 'LIMIT'

        params.update({
                    'symbol': coin,
                    'side': 'buy',
                    'quantity': '{0:4f}'.format(amount).strip(),
                  })

        return self._private_api('POST', '/api/v3/order', params)

    def sell(self, coin, amount, price=None):
        debugger.debug('{}::: Parameters=[{}, {}, {}], function name=[sell]'.format(self.name, coin, amount, price))

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
        binance_qtz = self._get_step_size(symbol).data[1]
        return Decimal(10) ** -4 if binance_qtz < Decimal(10) ** -4 else binance_qtz

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        debugger.debug('{}::: Parameters=[{}, {}, {}, {}], function name=[base_to_alt]'.format(
            self.name, currency_pair, btc_amount, alt_amount, td_fee, tx_fee
        ))
        currency_pair = self._symbol_localizing(currency_pair)
        base_market, coin = currency_pair.split('_')

        symbol = self._sai_symbol_converter(currency_pair)
        result_object = self.buy(symbol, alt_amount)

        if result_object.success:
            alt_amount *= 1 - Decimal(td_fee)
            alt_amount -= Decimal(tx_fee[coin])
            alt_amount = alt_amount.quantize(self.bnc_btm_quantizer(currency_pair), rounding=ROUND_DOWN)

            result_object.data = alt_amount

        return result_object

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        debugger.debug('{}::: Parameters=[{}, {}, {}], function name=[alt_to_base]'.format(
            self.name, currency_pair, btc_amount, alt_amount
        ))
        currency_pair = self._symbol_localizing(currency_pair)

        symbol = self._sai_symbol_converter(currency_pair)
        for _ in range(10):
            result_object = self.sell(symbol, alt_amount)

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    def get_ticker(self, market):
        symbol = self._sai_symbol_converter(market)
        for _ in range(3):
            result_object = self._public_api('/api/v3/ticker/price', {'symbol': symbol})
            if result_object.success:
                break
        time.sleep(result_object.wait_time)

        return result_object

    def withdraw(self, coin, amount, to_address, payment_id=None):
        debugger.debug('{}::: Parameters=[{}, {}, {}, {}], function name=[withdraw]'.format(self.name, coin, amount,
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

    def get_candle(self):
        candle_dict = deepcopy(self.data_store.candle_queue)
    
        if not candle_dict:
            return ExchangeResult(False, '', 'candle data is not yet stored', 1)
    
        rows = ['timestamp', 'open', 'close', 'high', 'low', 'volume']
    
        result_dict = dict()
        for symbol, candle_list in candle_dict.items():
            history = {key_: list() for key_ in rows}
            for candle in candle_list:
                for key, item in candle.items():
                    history[key].append(item)
            result_dict[symbol] = history
    
        return ExchangeResult(True, result_dict)

    async def _async_private_api(self, method, path, extra=None):
        debugger.debug('{}::: Parameters=[{}, {}, {}], function name=[_async_private_api]'.format(self.name, method, path, extra))

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

                if 'msg' in response:
                    msg = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['msg'], path, extra)
                    debugger.debug(msg)
                    return ExchangeResult(False, '', msg, 1)

                else:
                    return ExchangeResult(True, response, '', 0)

            except Exception as ex:
                msg = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, ex, path, extra)
                debugger.debug(msg)
                return ExchangeResult(False, '', 1)

    async def _async_public_api(self, path, extra=None):
        debugger.debug('{}::: Parameters=[{}, {},], function name=[_async_public_api]'.format(self.name, path, extra))

        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession() as session:
            rq = await session.get(self._base_url + path, params=extra)

        try:
            response = json.loads(await rq.text())

            if 'msg' in response:
                msg = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, response['msg'], path, extra)
                debugger.debug(msg)
                return ExchangeResult(False, '', msg, 1)

            else:
                return ExchangeResult(True, response, '', 0)

        except Exception as ex:
            msg = '{}::: ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(self.name, ex, path, extra)
            debugger.debug(msg)
            return ExchangeResult(False, '', msg, 1)

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
            result_object = await self._async_public_api('/api/v3/depth', {'symbol': symbol})
            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def get_deposit_addrs(self, coin_list=None):
        if coin_list is None:
            coin_list = list(self.exchange_info.keys())
            
        try:
            result_message = str()
            return_deposit_dict = dict()
            coin_list.append('BTC_BTC')

            for symbol in coin_list:
                base_, coin = symbol.split('_')
                coin = self._symbol_customizing(coin)

                get_deposit_result_object = await self._get_deposit_addrs(coin)
                
                if not get_deposit_result_object.success:
                    result_message += '[{}]해당 코인은 값을 가져오는데 실패했습니다.\n'.format(get_deposit_result_object.message)
                    continue
                    
                elif get_deposit_result_object.data['success'] is False:
                    result_message += '[{}]해당 코인은 점검 중입니다.\n'.format(coin)
                    continue
                
                return_deposit_dict[coin] = get_deposit_result_object.data['address']

                if 'addressTag' in get_deposit_result_object.data:
                    return_deposit_dict[coin + 'TAG'] = get_deposit_result_object.data['addressTag']
            return ExchangeResult(True, return_deposit_dict, result_message, 0)

        except Exception as ex:
            return ExchangeResult(False, '', '{}::: ERROR_BODY=[입금 주소를 가져오는데 실패했습니다. {}]'.format(self.name, ex), 1)

    async def get_avg_price(self, coins):  # 내거래 평균매수가
        # 해당 함수는 현재 미사용 상태
        try:
            amount_price_list, res_value = (list() for _ in range(2))
            for coin in coins:
                total_price, bid_count, total_amount = (int() for _ in range(3))
                
                sp = coin.split('_')
                coin = sp[1] + sp[0]
                for _ in range(10):
                    history_result_object = await self._async_private_api(
                        'GET', '/api/v3/allOrders', {'symbol': coin})

                    if history_result_object.success:
                        break

                    time.sleep(1)

                else:
                    # history 값을 가져오는데 실패하는 경우.
                    return history_result_object

                history = history_result_object.data
                history.reverse()
                for _data in history:
                    if not _data['status'] == 'FILLED':
                        # 매매 완료 상태가 아닌 경우 continue
                        continue
                    
                    trading_type = _data['side']
                    n_price = float(_data['price'])
                    price = Decimal(n_price - (n_price * 0.1)).quantize(Decimal(10) ** -8)
                    amount = Decimal(_data['origQty']).quantize(Decimal(10) ** -8)
                    if trading_type == 'BUY':
                        amount_price_list.append({
                            'price': price,
                            'amount': amount
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

            return ExchangeResult(True, res_value, '', 0)

        except Exception as ex:
            return ExchangeResult(False, '', '{}::: 평균 값을 가져오는데 실패했습니다. [{}]'.format(self.name, ex), 1)

    async def get_trading_fee(self):
        return ExchangeResult(True, 0.001, '', 0)

    async def get_transaction_fee(self):
        fees = dict()
        try:

            for _ in range(3):
                async with aiohttp.ClientSession() as session:
                    rq = await session.get('https://www.binance.com/assetWithdraw/getAllAsset.html')
                    data_list = json.loads(await rq.text())

                    if not data_list:
                        time.sleep(3)
                        continue

                for f in data_list:
                    symbol = self._symbol_customizing(f['assetCode'])
                    fees[symbol] = Decimal(f['transactionFee']).quantize(Decimal(10)**-8)

                return ExchangeResult(True, fees, '', 0)
            else:
                return ExchangeResult(False, '', '{}::: ERROR_BODY=[출금 비용을 가져오는데 실패했습니다.]'.format(self.name), 60)

        except Exception as ex:
            return ExchangeResult(False, '', '{}::: ERROR_BODY=[출금 비용을 가져오는데 실패했습니다. {}]'.format(self.name, ex), 60)

    async def get_balance(self):
        result_object = await self._get_balance()

        if result_object.success:
            balance = dict()
            for bal in result_object.data['balances']:
                symbol = self._symbol_customizing(bal['asset'])
                if float(bal['free']) > 0:
                    balance[symbol.upper()] = Decimal(bal['free']).quantize(Decimal(10)**-8)

            result_object.data = balance

        return result_object
    
    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        try:
            pairs = [(self._symbol_localizing(pair.split('_')[1]) + pair.split('_')[0]).lower()
                     for pair in self._coin_list]
                
            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, '', 'orderbook data is not yet stored', 1)

            avg_orderbook = dict()
            for pair in pairs:
                pair = pair.upper()
                if pair == 'BTCBTC':
                    continue
                
                orderbook_list = deepcopy(self.data_store.orderbook_queue.get(pair, None))
                
                if orderbook_list is None:
                    continue
                
                data_dict = dict(bids=list(),
                                 asks=list())
                
                for data in orderbook_list:
                    data_dict['bids'].append(data['bids'])
                    data_dict['asks'].append(data['asks'])

                avg_orderbook[pair] = dict()
                
                for order_type in ['asks', 'bids']:
                    sum_ = Decimal(0.0)
                    total_coin_num = Decimal(0.0)
                    for data in data_dict[order_type]:
                        price = data['price']
                        alt_coin_num = data['amount']
                        sum_ += Decimal(price) * Decimal(alt_coin_num)
                        total_coin_num += Decimal(alt_coin_num)
                        if sum_ > btc_sum:
                            break
                    avg_orderbook[pair][order_type] = (sum_ / total_coin_num).quantize(
                        Decimal(10) ** -8)

            return ExchangeResult(True, avg_orderbook)

        except Exception as ex:
            return ExchangeResult(False, '', '{}::: ERROR_BODY=[{}], URL=[get_curr_avg_orderbook]'.format(self.name, ex), 1)

    async def compare_orderbook(self, other, coins, default_btc=1):
        for _ in range(3):
            binance_result_object, other_result_object = await asyncio.gather(
                self.get_curr_avg_orderbook(coins, default_btc),
                other.get_curr_avg_orderbook(coins, default_btc)
            )

            if 'BTC' in coins:
                # 나중에 점검
                coins.remove('BTC')

            success = (binance_result_object.success and other_result_object.success)
            wait_time = max(binance_result_object.wait_time, other_result_object.wait_time)

            if success:
                m_to_s, s_to_m = (dict() for _ in range(2))

                for currency_pair in coins:
                    m_ask = binance_result_object.data[currency_pair]['asks']
                    s_bid = other_result_object.data[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                    m_bid = binance_result_object.data[currency_pair]['bids']
                    s_ask = other_result_object.data[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                res = binance_result_object.data, other_result_object.data, {'m_to_s': m_to_s, 's_to_m': s_to_m}

                return ExchangeResult(True, res, '', 0)
            else:
                time.sleep(wait_time)

        else:
            error_message = binance_result_object.message + '\n' + other_result_object.message
            return ExchangeResult(False, '', error_message, 1)
