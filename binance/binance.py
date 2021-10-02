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

from Exchanges.settings import Consts, BaseMarkets, BaseTradeType, SaiOrderStatus
from Exchanges.messages import WarningMessage, MessageDebug
from Exchanges.binance.util import sai_to_binance_symbol_converter, binance_to_sai_symbol_converter, \
    sai_to_binance_trade_type_converter, sai_to_binance_symbol_converter_in_subscriber
from Exchanges.binance.setting import Urls, OrderStatus
from Exchanges.abstracts import BaseExchange
from Exchanges.objects import ExchangeResult, DataStore
from Exchanges.binance.subscriber import BinanceSubscriber
from Util.pyinstaller_patch import debugger

decimal.getcontext().prec = 8


class Binance(BaseExchange):
    name = 'Binance'

    def __init__(self, key, secret):
        self._key = key
        self._secret = secret
        
        self.exchange_info = None
        self._get_exchange_info()
        self._lot_sizes = self._set_lot_sizes()
        self.data_store = DataStore()

        self._lock_dic = {
            Consts.ORDERBOOK: threading.Lock(),
            Consts.CANDLE: threading.Lock()
        }
        
        self._subscriber = BinanceSubscriber(self.data_store, self._lock_dic)

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
                if path == Urls.WITHDRAW:
                    rq = requests.post(Urls.BASE + path, params=query, headers={"X-MBX-APIKEY": self._key})
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
                self.exchange_info = result_object.data
                break

            time.sleep(result_object.wait_time)
        else:
            return result_object

        step_size = dict()

        for each in result_object.data['symbols']:
            symbol = each['symbol']
            sai_symbol = binance_to_sai_symbol_converter(symbol)
            market, coin = sai_symbol.split('_')
            step_size.update({
                coin: each['filters'][2]['stepSize']
            })

        self.exchange_info = step_size

        return True

    def _get_step_size(self, symbol):
        symbol = self._symbol_localizing(symbol)

        step_size = Decimal(self.exchange_info[symbol]).normalize()

        return ExchangeResult(True, step_size, '', 0)

    def _set_lot_sizes(self):
        lot_size_info = dict()
        for each in self.exchange_info['symbols']:
            symbol = each['symbol']
            filter_data = each['filters']
            lot_size_info.setdefault(symbol, dict())
            for filter_ in filter_data:
                filter_type = filter_['filterType']
                if filter_type == 'LOT_SIZE':
                    min_ = Decimal(filter_.get('minQty', int())).quantize(Decimal(10) ** -8)
                    max_ = Decimal(filter_.get('maxQty', int())).quantize(Decimal(10) ** -8)
                    step_size = Decimal(filter_.get('stepSize', int())).quantize(Decimal(10) ** -8)
                    lot_size_info[symbol] = {
                        'min_quantity': min_,
                        'max_quantity': max_,
                        'step_size': step_size
                    }
                    break
        return lot_size_info

    def set_subscriber(self):
        self._subscriber = BinanceSubscriber(self.data_store, self._lock_dic)

    def get_precision(self, pair=None):
        pair = self._symbol_localizing(pair)

        if pair in self.exchange_info:
            precision = int(math.log10(float(self.exchange_info[pair])))
            return ExchangeResult(True, precision)
        else:
            return ExchangeResult(False, message=WarningMessage.PRECISION_NOT_FOUND.format(name=self.name), wait_time=60)

    def get_available_symbols(self):
        result = list()
        for data in self.exchange_info['symbols']:
            market = data.get('quoteAsset')
            coin = data.get('baseAsset')

            if not market or not coin:
                continue

            result.append('{}_{}'.format(market, coin))

        return result

    def buy(self, symbol, amount, trade_type, price=None):
        debugger.debug('Binance, buy::: {}, {}, {}'.format(symbol, amount, price))
        params = dict()

        binance_trade_type = sai_to_binance_trade_type_converter(trade_type)
        binance_symbol = sai_to_binance_symbol_converter(symbol)

        step_size = self._lot_sizes[symbol]['step_size']

        decimal_amount = Decimal(amount)
        buy_size = (decimal_amount - Decimal(decimal_amount % step_size)).quantize(Decimal(10) ** - 8)
        params.update({
                    'symbol': binance_symbol,
                    'side': 'buy',
                    'quantity': '{0:4f}'.format(buy_size).strip(),
                    'type': binance_trade_type
                  })

        result = self._private_api(Consts.POST, Urls.ORDER, params)

        if result.success:
            price = result.data['price']
            amount = result.data['origQty']
            result.data.update({
                'sai_average_price': price,
                'sai_amount': amount,
                'sai_order_id': result.data['orderId']

            })

        return result

    def sell(self, symbol, amount, trade_type, price=None):
        debugger.debug('Binance, sell::: {}, {}, {}'.format(symbol, amount, price))
        params = dict()

        binance_trade_type = sai_to_binance_trade_type_converter(trade_type)
        binance_symbol = sai_to_binance_symbol_converter(symbol)

        step_size = self._lot_sizes[symbol]['step_size']
        decimal_amount = Decimal(amount)
        sell_size = (decimal_amount - Decimal(decimal_amount % step_size)).quantize(Decimal(10) ** - 8)

        params.update({
                    'type': binance_trade_type,
                    'symbol': binance_symbol,
                    'side': 'sell',
                    'quantity': '{0:4f}'.format(sell_size).strip(),
                  })

        result = self._private_api(Consts.POST, Urls.ORDER, params)

        if result.success:
            price = result.data['price']
            amount = result.data['origQty']
            result.data.update({
                'sai_average_price': price,
                'sai_amount': amount,
                'sai_order_id': result.data['orderId']
            })

        return result

    def fee_count(self):
        return 1

    def bnc_btm_quantizer(self, symbol):
        binance_symbol = sai_to_binance_symbol_converter(symbol)
        binance_qtz = self._get_step_size(binance_symbol).data[1]
        return Decimal(10) ** -4 if binance_qtz < Decimal(10) ** -4 else binance_qtz

    def base_to_alt(self, symbol, btc_amount, alt_amount, td_fee, tx_fee):
        coin = symbol.split('_')[1]
        binance_symbol = sai_to_binance_symbol_converter(symbol)
        result_object = self.buy(binance_symbol, alt_amount, BaseTradeType.MARKET)

        if result_object.success:
            alt_amount *= 1 - Decimal(td_fee)
            alt_amount -= Decimal(tx_fee[coin])
            alt_amount = alt_amount.quantize(self.bnc_btm_quantizer(symbol), rounding=ROUND_DOWN)

            result_object.data = alt_amount

        return result_object

    def alt_to_base(self, symbol, btc_amount, alt_amount):
        binance_symbol = binance_to_sai_symbol_converter(symbol)
        for _ in range(10):
            result_object = self.sell(binance_symbol, alt_amount, BaseTradeType.MARKET)

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    def get_ticker(self, symbol):
        binance_symbol = binance_to_sai_symbol_converter(symbol)
        for _ in range(3):
            result_object = self._public_api(Urls.TICKER, {'symbol': binance_symbol})
            if result_object.success:
                result_object.data = {'sai_price': result_object.data[0]['trade_price']}
                break
        time.sleep(result_object.wait_time)

        return result_object

    def get_order_history(self, order_id, additional):
        debugger.debug('Binance, get_order_history::: {}, {}'.format(order_id, additional))

        params = dict(orderId=order_id)
        if additional:
            if 'symbol' in additional:
                additional['symbol'] = sai_to_binance_symbol_converter(additional['symbol'])
            params.update(additional)

        result = self._private_api(Consts.GET, Urls.ORDER, params)

        if result.success:
            cummulative_quote_qty = Decimal(result.data['cummulativeQuoteQty']).quantize(Decimal(10) ** -6,
                                                                                         rounding=ROUND_DOWN)
            origin_qty = Decimal(result.data['origQty']).quantize(Decimal(10) ** -6, rounding=ROUND_DOWN)
            additional = {'sai_status': SaiOrderStatus.CLOSED if result.data['status'] == OrderStatus.FILLED else SaiOrderStatus.ON_TRADING,
                          'sai_average_price': cummulative_quote_qty,
                          'sai_amount': origin_qty}

            result.data = additional

        return result

    def withdraw(self, coin, amount, to_address, payment_id=None):
        coin = self._symbol_localizing(coin)
        params = {'coin': coin, 'address': to_address,
                  'amount': Decimal(amount).quantize(Decimal(10) ** - 8), 'name': 'SAICDiffTrader'}

        if payment_id:
            tag_dic = {'addressTag': payment_id}
            params.update(tag_dic)

        return self._private_api(Consts.POST, Urls.WITHDRAW, params)

    def set_subscribe_candle(self, symbol):
        """
            subscribe candle.
            coin: it can be list or string, [xrpbtc, ethbtc] or 'xrpbtc'
        """
        for _ in range(10):
            time.sleep(1)
            if self._subscriber.keep_running:
                break

        binance_symbol_list = list(map(sai_to_binance_symbol_converter_in_subscriber, symbol)) if isinstance(symbol, list) \
            else sai_to_binance_symbol_converter_in_subscriber(symbol)
        with self._lock_dic['candle']:
            self._subscriber.subscribe_candle(binance_symbol_list)

        return True

    def set_subscribe_orderbook(self, symbol):
        """
            subscribe orderbook.
            coin: it can be list or string, [xrpbtc, ethbtc] or 'xrpbtc'
        """
        for _ in range(10):
            time.sleep(1)
            if self._subscriber.keep_running:
                break

        binance_symbol_list = list(map(sai_to_binance_symbol_converter_in_subscriber, symbol)) if isinstance(symbol, list) \
            else sai_to_binance_symbol_converter_in_subscriber(symbol)
        with self._lock_dic['orderbook']:
            self._subscriber.subscribe_orderbook(binance_symbol_list)

        return True

    def get_orderbook(self):
        with self._lock_dic['orderbook']:
            data_dic = self.data_store.orderbook_queue
            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, message=WarningMessage.ORDERBOOK_NOT_STORED.format(name=self.name),
                                    wait_time=1)

            return ExchangeResult(True, data_dic)

    def get_candle(self, symbol):
        binance_symbol = sai_to_binance_symbol_converter(symbol)
        with self._lock_dic['candle']:
            candle_dict = self.data_store.candle_queue.get(binance_symbol, None)
        
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

    async def get_deposit_addrs(self):
        debugger.debug('Binance::: get_deposit_addrs')

        able_to_trading_coin_list = list()
        for data in self.exchange_info['symbols']:
            if data['status'] == 'TRADING':
                able_to_trading_coin_list.append(data['baseAsset'])

        try:
            result_message = str()
            return_deposit_dict = dict()
            for coin in able_to_trading_coin_list:
                coin = self._symbol_customizing(coin)

                get_deposit_result_object = await self._get_deposit_addrs(coin)
                
                if not get_deposit_result_object.success:
                    result_message += '[{}]해당 코인은 값을 가져오는데 실패했습니다.\n'.format(get_deposit_result_object.message)
                    continue
                    
                elif get_deposit_result_object.data['success'] is False:
                    result_message += '[{}]해당 코인은 점검 중입니다.\n'.format(coin)
                    continue
                
                address = get_deposit_result_object.data.get('address')
                if address:
                    return_deposit_dict[coin] = address

                address_tag = get_deposit_result_object.data.get('tag')
                if 'addressTag' in get_deposit_result_object.data:
                    return_deposit_dict[coin + 'TAG'] = address_tag
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
        result = self._private_api('GET', Urls.GET_ALL_INFORMATION)

        if result.success:
            fees = dict()
            for each in result.data:
                coin = each['coin']
                for network_info in each['networkList']:
                    network_coin = network_info['coin']

                    if coin == network_coin:
                        withdraw_fee = network_info['withdrawFee']
                        fees.update({coin: Decimal(withdraw_fee).quantize(Decimal(10) ** -8)})
                        break

            result.data = fees

        return result

    async def get_balance(self):
        result_object = await self._get_balance()

        if result_object.success:
            balance = dict()
            for bal in result_object.data['balances']:
                coin = self._symbol_customizing(bal['asset'])
                if float(bal['free']) > 0:
                    balance[coin.upper()] = Decimal(bal['free']).quantize(Decimal(10)**-8)

            result_object.data = balance

        return result_object
    
    async def get_curr_avg_orderbook(self, symbol_list, btc_sum=1):
        try:
            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, message=WarningMessage.ORDERBOOK_NOT_STORED.format(name=self.name), wait_time=1)

            avg_orderbook = dict()
            for symbol in symbol_list:
                binance_symbol = sai_to_binance_symbol_converter(symbol)

                with self._lock_dic['orderbook']:
                    orderbook_list = self.data_store.orderbook_queue.get(binance_symbol, None)
                    if orderbook_list is None:
                        continue
                    data_dict = dict(bids=list(),
                                     asks=list())
                    
                    for data in orderbook_list:
                        data_dict[Consts.BIDS].append(data[Consts.BIDS])
                        data_dict[Consts.ASKS].append(data[Consts.ASKS])
    
                    avg_orderbook[symbol] = dict()
                    
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
                        avg_orderbook[symbol][order_type] = (sum_ / total_coin_num).quantize(
                            Decimal(10) ** -8)

            return ExchangeResult(True, avg_orderbook)

        except:
            debugger.exception('FATAL: Binance, get_curr_avg_orderbook')
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    async def compare_orderbook(self, other_exchange, symbol_list, default_btc=1):
        for _ in range(3):
            binance_result_object, other_result_object = await asyncio.gather(
                self.get_curr_avg_orderbook(symbol_list, default_btc),
                other_exchange.get_curr_avg_orderbook(symbol_list, default_btc)
            )

            success = (binance_result_object.success and other_result_object.success)
            wait_time = max(binance_result_object.wait_time, other_result_object.wait_time)

            if success:
                m_to_s, s_to_m = dict(), dict()
                for symbol in symbol_list:
                    m_ask = binance_result_object.data[symbol][Consts.ASKS]
                    s_bid = other_result_object.data[symbol][Consts.BIDS]
                    m_to_s[symbol] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                    m_bid = binance_result_object.data[symbol][Consts.BIDS]
                    s_ask = other_result_object.data[symbol][Consts.ASKS]
                    s_to_m[symbol] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                res = binance_result_object.data, other_result_object.data, {Consts.PRIMARY_TO_SECONDARY: m_to_s,
                                                                             Consts.SECONDARY_TO_PRIMARY: s_to_m}

                return ExchangeResult(True, res)
            else:
                time.sleep(wait_time)

        else:
            error_message = binance_result_object.message + '\n' + other_result_object.message
            return ExchangeResult(False, message=error_message, wait_time=1)
