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
from Exchanges.messages import WarningMessage, DebugMessage
from Exchanges.binance.util import sai_to_binance_symbol_converter, binance_to_sai_symbol_converter, \
    sai_to_binance_trade_type_converter, sai_to_binance_symbol_converter_in_subscriber, _symbol_customizing, _symbol_localizing
from Exchanges.binance.setting import Urls, OrderStatus, DepositStatus
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
        self.all_details = None
        self._get_exchange_info()
        self._get_all_asset_details()
        self._lot_sizes = self._set_lot_sizes()
        self.data_store = DataStore()

        self._lock_dic = {
            Consts.ORDERBOOK: threading.Lock(),
            Consts.CANDLE: threading.Lock()
        }

        self._subscriber = None

    def _get_results(self, request, path, extra, fn):
        try:
            result = json.loads(request)
        except:
            debugger.debug(DebugMessage.FATAL.format(name=self.name, fn=fn))
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

        raw_error_message = result.get('msg', None)

        if raw_error_message is None:
            return ExchangeResult(True, result)
        else:
            error_message = WarningMessage.FAIL_RESPONSE_DETAILS.format(name=self.name, body=raw_error_message,
                                                                        path=path, parameter=extra)
            return ExchangeResult(False, message=error_message, wait_time=1)

    def _public_api(self, path, extra=None):
        if extra is None:
            extra = dict()

        rq = requests.get(Urls.BASE + path, params=extra)
        return self._get_results(rq, path, extra, fn='_public_api')

    def _private_api(self, method, path, extra=None):
        if extra is None:
            extra = dict()

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

        return self._get_results(rq, path, extra, fn='_private_api')

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

    def _get_all_asset_details(self):
        for _ in range(3):
            result_object = self._private_api('GET', Urls.GET_ALL_INFORMATION)
            if result_object.success:
                result = dict()
                for each in result_object.data:
                    coin = each.pop('coin', None)

                    if coin:
                        result.update({coin: each})
                self.all_details = result
                break

            time.sleep(result_object.wait_time)
        else:
            return result_object

    def _get_step_size(self, symbol, amount):
        step_size = self._lot_sizes.get(symbol, dict()).get('step_size')
        
        if not step_size:
            sai_symbol = binance_to_sai_symbol_converter(symbol)
            return ExchangeResult(False, message=WarningMessage.STEP_SIZE_NOT_FOUND.format(
                name=self.name,
                sai_symbol=sai_symbol,
            ))
        step_size = self._lot_sizes[symbol]['step_size']

        decimal_amount = Decimal(amount)
        stepped_amount = (decimal_amount - Decimal(decimal_amount % step_size)).quantize(Decimal(10) ** - 8)

        return ExchangeResult(True, stepped_amount)

    def _is_available_lot_size(self, symbol, amount):
        minimum = self._lot_sizes[symbol]['min_quantity']
        maximum = self._lot_sizes[symbol]['max_quantity']
        if not minimum <= amount <= maximum:
            msg = WarningMessage.WRONG_LOT_SIZE.format(
                name=self.name,
                market=symbol,
                minimum=minimum,
                maximum=maximum
            )
            return ExchangeResult(False, message=msg)
        
        return ExchangeResult(True)
        
    def _is_available_min_notional(self, symbol, price, amount):
        total_price = Decimal(price * amount)
    
        minimum = self._lot_sizes[symbol]['min_notional']
        if not minimum <= total_price:
            msg = WarningMessage.WRONG_MIN_NOTIONAL.format(
                name=self.name,
                symbol=symbol,
                min_notional=minimum,
            )
            return ExchangeResult(False, message=msg)

    def _trading_validator(self, symbol, amount):
        ticker_object = self.get_ticker(symbol)
        if not ticker_object.success:
            return ticker_object

        price = ticker_object.data['sai_price']

        lot_size_result = self._is_available_lot_size(symbol, amount)

        if not lot_size_result.success:
            return lot_size_result
        
        min_notional_result = self._is_available_min_notional(symbol, price, amount)
        
        if not min_notional_result.success:
            return min_notional_result
        
        step_size_result = self._get_step_size(symbol, amount)

        return step_size_result

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
                    lot_size_info[symbol].update({
                        'min_quantity': min_,
                        'max_quantity': max_,
                        'step_size': step_size
                    })
                    break
                elif filter_type == 'MIN_NOTIONAL':
                    min_notional = Decimal(filter_.get('minNotional', int())).quantize(Decimal(10) ** -8)
                    lot_size_info[symbol].update({
                        'min_notional': min_notional
                    })
        return lot_size_info

    def fee_count(self):
        return 1

    def set_subscriber(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscriber", data=str(locals())))
        self._subscriber = BinanceSubscriber(self.data_store, self._lock_dic)

    def set_subscribe_candle(self, symbol):
        """
            subscribe candle.
            coin: it can be list or string, [xrpbtc, ethbtc] or 'xrpbtc'
        """
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_candle", data=str(locals())))
        for _ in range(10):
            time.sleep(1)
            if self._subscriber.keep_running:
                break

        binance_symbol_list = list(map(sai_to_binance_symbol_converter_in_subscriber, symbol)) if isinstance(symbol,
                                                                                                             list) \
            else sai_to_binance_symbol_converter_in_subscriber(symbol)
        with self._lock_dic['candle']:
            self._subscriber.subscribe_candle(binance_symbol_list)

        return True

    def set_subscribe_orderbook(self, symbol):
        """
            subscribe orderbook.
            coin: it can be list or string, [xrpbtc, ethbtc] or 'xrpbtc'
        """
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_orderbook", data=str(locals())))
        for _ in range(10):
            time.sleep(1)
            if self._subscriber.keep_running:
                break

        binance_symbol_list = list(map(sai_to_binance_symbol_converter_in_subscriber, symbol)) if isinstance(symbol,
                                                                                                             list) \
            else sai_to_binance_symbol_converter_in_subscriber(symbol)
        with self._lock_dic['orderbook']:
            self._subscriber.subscribe_orderbook(binance_symbol_list)

        return True

    def get_orderbook(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_orderbook", data=str(locals())))
        with self._lock_dic['orderbook']:
            data_dic = self.data_store.orderbook_queue
            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, message=WarningMessage.ORDERBOOK_NOT_STORED.format(name=self.name),
                                      wait_time=1)

            return ExchangeResult(True, data_dic)

    def get_candle(self, symbol):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_candle", data=str(locals())))
        binance_symbol = sai_to_binance_symbol_converter(symbol)
        with self._lock_dic['candle']:
            candle_dict = self.data_store.candle_queue.get(binance_symbol, None)

            if not candle_dict:
                return ExchangeResult(False, message=WarningMessage.CANDLE_NOT_STORED.format(name=self.name),
                                      wait_time=1)

            rows = ['timestamp', 'open', 'close', 'high', 'low', 'volume']
            result_dict = dict()
            for symbol, candle_list in candle_dict.items():
                history = {key_: list() for key_ in rows}
                for candle in candle_list:
                    for key, item in candle.items():
                        history[key].append(item)
                result_dict[symbol] = history

        return ExchangeResult(True, result_dict)

    def get_ticker(self, symbol):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_ticker", data=str(locals())))
        binance_symbol = sai_to_binance_symbol_converter(symbol)
        result_object = self._public_api(Urls.TICKER, {'symbol': binance_symbol})
        if result_object.success:
            result_object.data = {'sai_price': result_object.data[0]['trade_price']}

        return result_object

    def get_available_symbols(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_available_symbols", data=str(locals())))
        result = list()
        for data in self.exchange_info['symbols']:
            market = data.get('quoteAsset')
            coin = data.get('baseAsset')

            if not market or not coin:
                continue

            result.append('{}_{}'.format(market, coin))

        return result

    def get_order_history(self, order_id, additional):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_order_history", data=str(locals())))

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

    def get_deposit_history(self, coin):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_deposit_history", data=str(locals())))
        params = dict(coin=coin, status=DepositStatus.SUCCESS)

        result = self._private_api(Consts.GET, Urls.GET_DEPOSIT_HISTORY, params)

        if result.success and result.data:
            latest_data = result.data[0]
            result_dict = dict(
                sai_deposit_amount=latest_data['amount'],
                sai_coin=latest_data['coin']
            )

            result.data = result_dict

        return result

    def buy(self, sai_symbol, amount, trade_type, price=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="buy", data=str(locals())))

        binance_trade_type = sai_to_binance_trade_type_converter(trade_type)
        symbol = sai_to_binance_symbol_converter(sai_symbol)

        trading_validation_result = self._trading_validator(symbol, amount)
        
        if not trading_validation_result.success:
            return trading_validation_result
        
        stepped_amount = trading_validation_result.data
        
        params = {
            'symbol': symbol,
            'side': 'buy',
            'quantity': stepped_amount,
            'type': binance_trade_type
        }
        
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

    def sell(self, sai_symbol, amount, trade_type, price=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="sell", data=str(locals())))
        params = dict()

        binance_trade_type = sai_to_binance_trade_type_converter(trade_type)
        symbol = sai_to_binance_symbol_converter(sai_symbol)

        trading_validation_result = self._trading_validator(symbol, amount)

        if not trading_validation_result.success:
            return trading_validation_result

        stepped_amount = trading_validation_result.data

        params.update({
                    'type': binance_trade_type,
                    'symbol': symbol,
                    'side': 'sell',
                    'quantity': stepped_amount
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

    def base_to_alt(self, coin, alt_amount, td_fee, tx_fee):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="base_to_alt", data=str(locals())))
        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[coin])
        alt_amount = alt_amount
        return alt_amount

    def alt_to_base(self, coin, btc_amount, alt_amount):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="alt_to_base", data=str(locals())))
        binance_symbol = sai_to_binance_symbol_converter(coin)
        for _ in range(10):
            result_object = self.sell(binance_symbol, alt_amount, BaseTradeType.SELL_MARKET)

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    def withdraw(self, coin, amount, to_address, payment_id=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="withdraw", data=str(locals())))
        coin = _symbol_localizing(coin)
        params = {'coin': coin, 'address': to_address,
                  'amount': Decimal(amount).quantize(Decimal(10) ** - 8), 'name': 'SAICDiffTrader'}

        if payment_id:
            tag_dic = {'addressTag': payment_id}
            params.update(tag_dic)

        result = self._private_api(Consts.POST, Urls.WITHDRAW, params)

        if result.success:
            sai_data = {
                'sai_id': result.data['id'],
            }
            result.data = sai_data

        return result

    async def _async_public_api(self, path, extra=None):
        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession() as session:
            rq = await session.get(Urls.BASE + path, params=extra)
            result_text = await rq.text()

            return self._get_results(result_text, path, extra, fn='_async_public_api')

    async def _async_private_api(self, method, path, extra=None):
        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession(headers={"X-MBX-APIKEY": self._key}) as session:
            query = self._sign_generator(extra)

            if method == Consts.GET:
                sig = query.pop('signature')
                query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)
                rq = await session.get(Urls.BASE + path + "?{}".format(query))

            else:
                rq = await session.post(Urls.BASE + path, data=query)

            result_text = await rq.text()
            return self._get_results(result_text, path, extra, fn='_async_private_api')

    async def _get_balance(self):
        for _ in range(3):
            result_object = await self._async_private_api(Consts.GET, Urls.ACCOUNT)
            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def get_deposit_addrs(self, coin_list=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_deposit_addrs", data=str(locals())))

        able_to_trading_coin_list = list()
        for data in self.exchange_info['symbols']:
            # check status coin is able to trading.
            if data['status'] == 'TRADING':
                able_to_trading_coin_list.append(data['baseAsset'])

        try:
            result_message = str()
            return_deposit_dict = dict()
            for coin in able_to_trading_coin_list:
                coin = _symbol_customizing(coin)

                get_deposit_result_object = await self._async_private_api(Consts.GET, Urls.DEPOSITS, {'coin': coin.lower()})
                
                if not get_deposit_result_object.success:
                    result_message += '[{}]해당 코인은 값을 가져오는데 실패했습니다.\n'.format(get_deposit_result_object.message)
                    continue

                coin_details = self.all_details.get(coin, None)

                if coin_details is not None:
                    able_deposit = coin_details['depositAllEnable']
                    able_withdrawal = coin_details['withdrawAllEnable']

                    if not able_deposit:
                        debugger.debug('Binance, [{}] 해당 코인은 입금이 막혀있는 상태입니다.'.format(coin))
                        continue

                    elif not able_withdrawal:
                        debugger.debug('Binance, [{}] 해당 코인은 출금이 막혀있는 상태입니다.'.format(coin))
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
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_transaction_fee", data=str(locals())))
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
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_balance", data=str(locals())))
        result_object = await self._get_balance()

        if result_object.success:
            balance = dict()
            for bal in result_object.data['balances']:
                coin = bal['asset']
                if float(bal['free']) > 0:
                    balance[coin.upper()] = Decimal(bal['free']).quantize(Decimal(10)**-8)

            result_object.data = balance

        return result_object
    
    async def get_curr_avg_orderbook(self, symbol_list, btc_sum=1):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_curr_avg_orderbook", data=str(locals())))
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
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    async def compare_orderbook(self, other_exchange, symbol_list, default_btc=1):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="compare_orderbook", data=str(locals())))
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
