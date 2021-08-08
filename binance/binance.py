import hmac
import math
import hashlib
import requests
import json
import time
import aiohttp
import asyncio
import threading
import decimal

from urllib.parse import urlencode
from decimal import Decimal, ROUND_DOWN, getcontext

from Exchanges.settings import Consts
from Exchanges.messages import WarningMessage, MessageDebug
from Exchanges.binance.util import sai_to_binance_converter, binance_to_sai_converter
from Exchanges.binance.setting import Urls
from Exchanges.abstracts import BaseExchange
from Exchanges.objects import ExchangeResult, DataStore
from Exchanges.binance.subscriber import BinanceSubscriber
from Util.pyinstaller_patch import debugger

decimal.getcontext().prec = 8


class Binance(BaseExchange):
    name = 'Binance'

    def __init__(self, key, secret, coin_list, time_):
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
            pairs = [binance_to_sai_converter(pair).lower()
                     for pair in self._coin_list]
            setattr(self._subscriber, 'candle_symbol_set', pairs)

        if self._subscriber.candle_receiver is None or not self._subscriber.candle_receiver.isAlive():
            self._subscriber.subscribe_candle(time_str)
    
    def _websocket_orderbook_settings(self):
        if not self._subscriber.orderbook_symbol_set:
            pairs = [binance_to_sai_converter(pair).lower() for pair in self._coin_list]
            setattr(self._subscriber, 'orderbook_symbol_set', pairs)
    
        if self._subscriber.orderbook_receiver is None or not self._subscriber.orderbook_receiver.isAlive():
            self._subscriber.subscribe_orderbook()

    def _public_api(self, path, extra=None):
        if extra is None:
            extra = dict()

        try:
            rq = requests.get(Urls.BASE + path, params=extra)
            response = rq.json()

            if 'msg' in response:
                message = MessageDebug.FAIL_RESPONSE_DETAILS.format(name=self.name, body=response['msg'],
                                                                    path=path, parameter=extra)
                debugger.debug(message)

                user_message = WarningMessage.FAIL_MESSAGE_BODY.format(name=self.name, message=response['msg'])
                return ExchangeResult(False, message=user_message, wait_time=1)
            else:
                return ExchangeResult(True, response)

        except:
            debugger.exception('FATAL: Binance, _public_api')
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    def _private_api(self, method, path, extra=None):
        if extra is None:
            extra = dict()

        try:
            query = self._sign_generator(extra)
            sig = query.pop('signature')
            query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)

            if method == Consts.GET:
                rq = requests.get(Urls.BASE + path, params=query, headers={"X-MBX-APIKEY": self._key})
            else:
                rq = requests.post(Urls.BASE + path, data=query, headers={"X-MBX-APIKEY": self._key})
            response = rq.json()

            if 'msg' in response:
                message = MessageDebug.FAIL_RESPONSE_DETAILS.format(name=self.name, body=response['msg'],
                                                                    path=path, parameter=extra)
                debugger.debug(message)

                user_message = WarningMessage.FAIL_MESSAGE_BODY.format(name=self.name, message=response['msg'])
                return ExchangeResult(False, wait_time=user_message, message=1)
            else:
                return ExchangeResult(True, response)

        except:
            debugger.exception('FATAL: Binance, _priavet_api')
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    def _get_server_time(self):
        return self._public_api(Urls.SERVER_TIME)

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
            result_object = self._public_api(Urls.EXCHANGE_INFO)
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
            precision = int(math.log10(float(self.exchange_info[pair])))
            return ExchangeResult(True, precision)
        else:
            return ExchangeResult(False, message=WarningMessage.PRECISION_NOT_FOUND.format(name=self.name), wait_time=60)

    def get_available_coin(self):
        return ExchangeResult(True, list(self.exchange_info.keys()))

    def buy(self, coin, amount, price=None):
        params = dict()
        params['type'] = Consts.MARKET.upper() if price is None else Consts.LIMIT.upper()

        params.update({
                    'symbol': coin,
                    'side': 'buy',
                    'quantity': '{0:4f}'.format(amount).strip(),
                  })

        return self._private_api(Consts.POST, Urls.ORDER, params)

    def sell(self, coin, amount, price=None):
        params = dict()

        params['type'] = Consts.MARKET.upper() if price is None else Consts.LIMIT.upper()

        params.update({
                    'symbol': coin,
                    'side': 'sell',
                    'quantity': '{}'.format(amount),
                  })

        return self._private_api(Consts.POST, Urls.ORDER, params)

    def fee_count(self):
        return 1

    def bnc_btm_quantizer(self, symbol):
        binance_qtz = self._get_step_size(symbol).data[1]
        return Decimal(10) ** -4 if binance_qtz < Decimal(10) ** -4 else binance_qtz

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        coin = currency_pair.split('_')[1]

        symbol = binance_to_sai_converter(currency_pair)
        result_object = self.buy(symbol, alt_amount)

        if result_object.success:
            alt_amount *= 1 - Decimal(td_fee)
            alt_amount -= Decimal(tx_fee[coin])
            alt_amount = alt_amount.quantize(self.bnc_btm_quantizer(symbol), rounding=ROUND_DOWN)

            result_object.data = alt_amount

        return result_object

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        symbol = binance_to_sai_converter(currency_pair)
        for _ in range(10):
            result_object = self.sell(symbol, alt_amount)

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    def get_ticker(self, market):
        symbol = binance_to_sai_converter(market)
        for _ in range(3):
            result_object = self._public_api(Urls.TICKER, {'symbol': symbol})
            if result_object.success:
                break
        time.sleep(result_object.wait_time)

        return result_object

    def withdraw(self, coin, amount, to_address, payment_id=None):
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

        return self._private_api(Consts.POST, Urls.WITHDRAW, params)

    def get_candle(self):
        with self._lock_dic['candle']:
            candle_dict = self.data_store.candle_queue
        
            if not candle_dict:
                return ExchangeResult(False, message=WarningMessage.CANDLE_NOT_STORED.format(name=self.name), wait_time=1)
        
            rows = ['timestamp', 'open', 'close', 'high', 'low', 'volume']
        
            result_dict = dict()
            for symbol, candle_list in candle_dict.items():
                history = {key_: list() for key_ in rows}
                for candle in candle_list:
                    for key, item in candle.items():
                        history[key].append(item)
                result_dict[symbol] = history
    
        return ExchangeResult(True, result_dict)

    def check_order(self, data, profit_object):
        return data

    async def _async_private_api(self, method, path, extra=None):
        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession(headers={"X-MBX-APIKEY": self._key}) as session:
            query = self._sign_generator(extra)

            try:
                if method == Consts.GET:
                    sig = query.pop('signature')
                    query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)
                    rq = await session.get(Urls.BASE + path + "?{}".format(query))

                else:
                    rq = await session.post(Urls.BASE + path, data=query)

                response = json.loads(await rq.text())

                if 'msg' in response:
                    message = MessageDebug.FAIL_RESPONSE_DETAILS.format(name=self.name, body=response['msg'],
                                                                        path=path, parameter=extra)
                    debugger.debug(message)
                    return ExchangeResult(False, message=message, wait_time=1)

                else:
                    return ExchangeResult(True, response)

            except:
                debugger.exception('FATAL: Binance, _async_private_api')
                return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    async def _async_public_api(self, path, extra=None):
        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession() as session:
            rq = await session.get(Urls.BASE + path, params=extra)

        try:
            response = json.loads(await rq.text())

            if 'msg' in response:
                message = MessageDebug.FAIL_RESPONSE_DETAILS.format(name=self.name, body=response['msg'],
                                                                    path=path, parameter=extra)
                debugger.debug(message)
                return ExchangeResult(False, message=message, wait_time=1)

            else:
                return ExchangeResult(True, response)

        except:
            debugger.exception('FATAL')
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    async def _get_balance(self):
        for _ in range(3):
            result_object = await self._async_private_api(Consts.GET, Urls.ACCOUNT)
            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def _get_deposit_addrs(self, symbol):
        for _ in range(3):
            result_object = await self._async_private_api(Consts.GET, Urls.DEPOSITS, {'asset': symbol})

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def _get_orderbook(self, symbol):
        for _ in range(3):
            result_object = await self._async_public_api(Urls.ORDERBOOK, {'symbol': symbol})
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
            return ExchangeResult(True, return_deposit_dict, result_message)

        except Exception as ex:
            debugger.exception('FATAL: Binance, get_deposit_addrs')

            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

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
                        Consts.GET, Urls.ALL_ORDERS, {'symbol': coin})

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

            return ExchangeResult(True, res_value)

        except Exception as ex:
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    async def get_trading_fee(self):
        return ExchangeResult(True, 0.001)

    async def get_transaction_fee(self):
        fees = dict()
        try:
            url = Urls.PAGE_BASE + Urls.TRANSACTION_FEE
            for _ in range(3):
                async with aiohttp.ClientSession() as session:
                    rq = await session.get(url)
                    data_list = json.loads(await rq.text())

                    if not data_list:
                        time.sleep(3)
                        continue

                for f in data_list:
                    symbol = self._symbol_customizing(f['assetCode'])
                    fees[symbol] = Decimal(f['transactionFee']).quantize(Decimal(10)**-8)

                return ExchangeResult(True, fees)
            else:
                return ExchangeResult(False, message=WarningMessage.TRANSACTION_FAILED.format(name=self.name), wait_time=60)

        except:
            debugger.exception('FATAL: Binance, get_transaction_fee')
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=60)

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
                return ExchangeResult(False, message=WarningMessage.ORDERBOOK_NOT_STORED.format(name=self.name), wait_time=1)

            avg_orderbook = dict()
            for pair in pairs:
                pair = pair.upper()
                if pair == 'BTCBTC':
                    continue
                with self._lock_dic['orderbook']:
                    orderbook_list = self.data_store.orderbook_queue.get(pair, None)
                    
                    if orderbook_list is None:
                        continue
                    
                    data_dict = dict(bids=list(),
                                     asks=list())
                    
                    for data in orderbook_list:
                        data_dict[Consts.BIDS].append(data[Consts.BIDS])
                        data_dict[Consts.ASKS].append(data[Consts.ASKS])
    
                    avg_orderbook[pair] = dict()
                    
                    for order_type in [Consts.ASKS, Consts.BIDS]:
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

        except:
            debugger.exception('FATAL: Binance, get_curr_avg_orderbook')
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

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
                    m_ask = binance_result_object.data[currency_pair][Consts.ASKS]
                    s_bid = other_result_object.data[currency_pair][Consts.BIDS]
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                    m_bid = binance_result_object.data[currency_pair][Consts.BIDS]
                    s_ask = other_result_object.data[currency_pair][Consts.ASKS]
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                res = binance_result_object.data, other_result_object.data, {Consts.PRIMARY_TO_SECONDARY: m_to_s,
                                                                             Consts.SECONDARY_TO_PRIMARY: s_to_m}

                return ExchangeResult(True, res)
            else:
                time.sleep(wait_time)

        else:
            error_message = binance_result_object.message + '\n' + other_result_object.message
            return ExchangeResult(False, message=error_message, wait_time=1)
