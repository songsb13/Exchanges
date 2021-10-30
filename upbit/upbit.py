import jwt
import time
import json
import aiohttp
import numpy as np
import asyncio
import requests
import threading

from urllib.parse import urlencode
from Util.pyinstaller_patch import debugger

from Exchanges.settings import Consts, SaiOrderStatus
from Exchanges.messages import WarningMessage as WarningMsg
from Exchanges.messages import DebugMessage

from Exchanges.upbit.setting import Urls, OrderStatus, DepositStatus, LocalConsts
from Exchanges.upbit.subscriber import UpbitSubscriber
from Exchanges.upbit.util import sai_to_upbit_symbol_converter, upbit_to_sai_symbol_converter, sai_to_upbit_trade_type_converter

from Exchanges.abstracts import BaseExchange
from Exchanges.objects import DataStore, ExchangeResult

from decimal import Decimal, ROUND_DOWN
import decimal

decimal.getcontext().prec = 8


class BaseUpbit(BaseExchange):
    name = 'Upbit'

    def __init__(self, key, secret):
        self._key = key
        self._secret = secret
        self.data_store = DataStore()
        
        self._lock_dic = {
            Consts.ORDERBOOK: threading.Lock(),
            Consts.CANDLE: threading.Lock()
        }

        self._subscriber = None

    def _get_results(self, request, path, extra, fn):
        try:
            res = json.loads(request)
        except:
            debugger.exception(DebugMessage.FATAL.format(name=self.name, fn=fn))
            return ExchangeResult(False, message=WarningMsg.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

        raw_error = res.get('error', dict())

        if not raw_error:
            return ExchangeResult(True, res)
        else:
            raw_error_message = raw_error.get('message', None)
            if raw_error_message is None:
                error_message = WarningMsg.FAIL_RESPONSE_DETAILS.format(name=self.name, body=raw_error_message,
                                                                        path=path, parameter=extra)
            else:
                error_message = WarningMsg.MESSAGE_NOT_FOUND.format(name=self.name)

            return ExchangeResult(False, message=error_message, wait_time=1)

    def _public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        
        url = Urls.BASE + path
        rq = requests.get(url, params=extra)

        return self._get_results(rq, path, extra, fn='public_api')

    def _private_api(self, method, path, extra=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="_private_api", data=extra))
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }
        
        if extra is not None:
            payload.update({'query': urlencode(extra)})

        authorization_token = self.get_jwt_token(payload)
        header = {'Authorization': authorization_token}
        url = Urls.BASE + path

        if method == Consts.POST:
            rq = requests.post(url=url, headers=header, data=extra)

        else:
            rq = requests.get(url=url, headers=header, params=extra)

        return self._get_results(rq, path, extra, fn='private_api')

    def _get_step_size(self, symbol, krw_price):
        market, coin = symbol.split('-')

        if market in ['BTC', 'USDT']:
            return ExchangeResult(True, LocalConsts.STEP_SIZE[market][0][1])

        for price, unit in LocalConsts.STEP_SIZE[market]:
            if krw_price >= price:
                decimal_price = Decimal(price)
                stepped_price = (decimal_price - Decimal(decimal_price % unit)).quantize(Decimal(10) ** - 8)
                return ExchangeResult(True, stepped_price)
        else:
            sai_symbol = upbit_to_sai_symbol_converter(symbol)  # for logging
            return ExchangeResult(False, message=WarningMsg.STEP_SIZE_NOT_FOUND.format(
                name=self.name,
                sai_symbol=sai_symbol,
            ))

    def _is_available_lot_size(self, symbol, krw_price, amount):
        market, coin = symbol.split('-')
        total_price = Decimal(krw_price * amount)

        minimum = LocalConsts.LOT_SIZES[market]['minimum']
        maximum = LocalConsts.LOT_SIZES[market]['maximum']
        if not minimum <= total_price <= maximum:
            msg = WarningMsg.WRONG_LOT_SIZE.format(
                name=self.name,
                market=market,
                minimum=minimum,
                maximum=maximum
            )
            return ExchangeResult(False, message=msg)

        return ExchangeResult(True)

    def _trading_validator(self, symbol, amount):
        """
            Args:
                symbol: KRW, BTC
                amount: amount, Decimal
            Returns:
                True or False
                messages if getting false
        """
        ticker_object = self.get_ticker(symbol)
        if not ticker_object.success:
            return ticker_object

        krw_price = ticker_object.data['sai_price']

        lot_size_result = self._is_available_lot_size(symbol, krw_price, amount)

        if not lot_size_result.success:
            return lot_size_result

        step_size_result = self._get_step_size(symbol, krw_price)

        return step_size_result

    def fee_count(self):
        return 1

    def get_jwt_token(self, payload):
        return 'Bearer {}'.format(jwt.encode(payload, self._secret, ).decode('utf8'))

    def set_subscriber(self):
        self._subscriber = UpbitSubscriber(self.data_store, self._lock_dic)

    def set_subscribe_candle(self, symbol):
        """
            subscribe candle.
            symbol: it can be list or string, [BTC-XRP, BTC-ETH] or 'BTC-XRP'
        """
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_candle", data=str(locals())))
        coin = list(map(sai_to_upbit_symbol_converter, symbol)) if isinstance(symbol, list) \
            else sai_to_upbit_symbol_converter(symbol)
        with self._lock_dic['candle']:
            self._subscriber.subscribe_candle(coin)

        return True

    def set_subscribe_orderbook(self, symbol):
        """
            subscribe orderbook.
            symbol: it can be list or string, [BTC-XRP, BTC-ETH] or 'BTC-XRP'
        """
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_orderbook", data=str(locals())))
        coin = list(map(sai_to_upbit_symbol_converter, symbol)) if isinstance(symbol, list) \
            else sai_to_upbit_symbol_converter(symbol)
        with self._lock_dic['orderbook']:
            self._subscriber.subscribe_orderbook(coin)

        return True

    def get_ticker(self, symbol):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_ticker", data=str(locals())))
        symbol = sai_to_upbit_symbol_converter(symbol)

        result = self._public_api(Urls.TICKER, {'markets': symbol})

        if result.success:
            result.data = {'sai_price': result.data[0]['trade_price']}

        return result

    def get_order_history(self, uuid, additional_parameter):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_order_history", data=str(locals())))
        params = dict(uuid=uuid)

        result = self._private_api(Consts.GET, Urls.ORDER, params)

        if result.success:
            price_list, amount_list = list(), list()
            for each in result.data['trades']:
                total_price = float(each['price']) * float(each['volume'])
                price_list.append(float(total_price))
                amount_list.append(float(each['volume']))

            if price_list:
                avg_price = float(sum(price_list) / len(price_list))
                total_amount = sum(amount_list)
                additional = {
                    'sai_status': SaiOrderStatus.CLOSED,
                    'sai_average_price': Decimal(avg_price).quantize(Decimal(10) ** -6),
                    'sai_amount': Decimal(total_amount).quantize(Decimal(10) ** -6, rounding=ROUND_DOWN)
                }

                result.data = additional
            else:
                result.success = False

        return result

    def get_deposit_history(self, coin):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_deposit_history", data=str(locals())))
        params = dict(
            currency=coin,
            state=DepositStatus.ACCEPTED
        )
        result = self._private_api(Consts.GET, Urls.GET_DEPOSIT_HISTORY, params)

        if result.success:
            latest_data = result.data[0]
            result_dict = dict(
                sai_deposit_amount=latest_data['amount'],
                sai_coin=latest_data['currency']
            )
            result.data = result_dict

        return result

    def get_available_symbols(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_available_symbols", data=''))
        result = self._public_api(Urls.CURRENCY)

        if result.success:
            result_list = list()
            for data in result.data:
                symbol = data.get('market')
                if symbol:
                    converted = upbit_to_sai_symbol_converter(symbol)
                    result_list.append(converted)
            else:
                return result_list

    def get_orderbook(self):
        with self._lock_dic['orderbook']:
            data_dic = self.data_store.orderbook_queue

            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, message=WarningMsg.ORDERBOOK_NOT_STORED.format(name=self.name),
                                      wait_time=1)
            return ExchangeResult(True, data_dic)

    def get_candle(self, symbol):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_candle", data=str(locals())))
        with self._lock_dic['candle']:
            upbit_symbol = sai_to_upbit_symbol_converter(symbol)
            result = self.data_store.candle_queue.get(symbol, None)
            if result is None:
                return ExchangeResult(False, message=WarningMsg.CANDLE_NOT_STORED.format(name=self.name), wait_time=1)
            return ExchangeResult(True, result)

    def withdraw(self, coin, amount, to_address, payment_id=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="withdraw", data=str(locals())))
        params = {
            'currency': coin,
            'address': to_address,
            'amount': str(amount),
        }

        if payment_id:
            params.update({'secondary_address': payment_id})

        result = self._private_api(Consts.POST, Urls.WITHDRAW, params)

        if result.success:
            sai_data = {
                'sai_id': result.data['uuid'],
            }
            result.data = sai_data

        return result
    
    def buy(self, sai_symbol, amount, trade_type, price=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="buy", data=str(locals())))
        upbit_trade_type = sai_to_upbit_trade_type_converter(trade_type)
        symbol = sai_to_upbit_symbol_converter(sai_symbol)
        params = {
            'market': symbol,
            'side': 'bid',
            'volume': amount,
            'ord_type': upbit_trade_type
        }
        if price:
            trading_validation_result = self._trading_validator(symbol, amount)

            if not trading_validation_result.success:
                return trading_validation_result
            stepped_price = trading_validation_result.data
            params.update(dict(price=stepped_price))
        
        return self._private_api(Consts.POST, Urls.ORDERS, params)
    
    def sell(self, sai_symbol, amount, trade_type, price=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="sell", data=str(locals())))
        upbit_trade_type = sai_to_upbit_trade_type_converter(trade_type)
        symbol = sai_to_upbit_symbol_converter(sai_symbol)
        params = {
            'market': symbol,
            'side': 'ask',
            'volume': amount,
            'ord_type': upbit_trade_type
        }
        if price:
            trading_validation_result = self._trading_validator(symbol, amount)

            if not trading_validation_result.success:
                return trading_validation_result
            stepped_price = trading_validation_result.data
            params.update(dict(price=stepped_price))
        
        return self._private_api(Consts.POST, Urls.ORDERS, params)
    
    def base_to_alt(self, coin, alt_amount, td_fee, tx_fee):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="base_to_alt", data=str(locals())))
        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[coin])
        alt_amount = alt_amount

        return alt_amount

    async def _async_public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        async with aiohttp.ClientSession() as s:
            url = Urls.BASE + path
            rq = await s.get(url, params=extra)

            result_text = await rq.text()
            return self._get_results(result_text, path, extra, fn='_async_public_api')

    async def _async_private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }
        
        if extra is not None:
            payload.update({'query': urlencode(extra)})

        authorization_token = self.get_jwt_token(payload)
        header = {'Authorization': authorization_token}
        url = Urls.BASE + path

        async with aiohttp.ClientSession() as s:
            if method == Consts.GET:
                rq = await s.get(url, headers=header, data=extra)
            else:
                rq = await s.post(url, headers=header, data=extra)

            result_text = await rq.text()
            return self._get_results(result_text, path, extra, fn='_async_private_api')

    async def get_transaction_fee(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_transaction_fee", data=str(locals())))
        result = requests.get(Urls.Web.BASE + Urls.Web.TRANSACTION_FEE_PAGE)
        raw_data = json.loads(result.text)

        success = raw_data.get('success', False)
        if not success:
            return ExchangeResult(False, '', message=WarningMsg.TRANSACTION_FAILED.format(name=self.name))

        data = json.loads(raw_data['data'])

        fees = dict()
        for each in data:
            coin = each['currency']
            fee = Decimal(each['withdrawFee']).quantize(Decimal(10) ** -6)
            fees.update({coin: fee})

        return ExchangeResult(True, fees)

    async def get_deposit_addrs(self, coin_list):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_deposit_addrs", data=str(locals())))
        result = await self._async_private_api(Consts.GET, Urls.DEPOSIT_ADDRESS)
        if result.success:
            result_dict = dict()
            for data in result.data:
                coin = data['currency']
                if coin not in coin_list:
                    continue

                able_result = await self._async_private_api(Consts.GET, Urls.ABLE_WITHDRAWS, {'currency': coin})

                if not result.success:
                    continue

                support_list = able_result.data['currency']['wallet_support']
                if 'withdraw' not in support_list or 'deposit' not in support_list:
                    continue

                deposit_address = data['deposit_address']

                if 'secondary_address' in data.keys() and data['secondary_address']:
                    result_dict[coin + 'TAG'] = data['secondary_address']

                result_dict[coin] = deposit_address

            result.data = result_dict

        return result

    async def get_trading_fee(self):
        dic_ = dict(KRW=0.0005, BTC=0.0025, USDT=0.0025)
        return ExchangeResult(True, dic_['BTC'])

    async def get_balance(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_balance", data=str(locals())))
        result = await self._async_private_api(Consts.GET, Urls.ACCOUNT)

        if result.success:
            result.data = {bal['currency']: bal['balance'] for bal in result.data}

        return result

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_curr_avg_orderbook", data=str(locals())))
        with self._lock_dic['orderbook']:
            data_dic = self.data_store.orderbook_queue
            
            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, message=WarningMsg.ORDERBOOK_NOT_STORED.format(name=self.name), wait_time=1)
            
            avg_order_book = dict()
            for pair, item in data_dic.items():
                sai_symbol = upbit_to_sai_symbol_converter(pair)
                avg_order_book[sai_symbol] = dict()
                
                for type_ in ['ask', 'bid']:
                    order_amount, order_sum = list(), 0
                    for data in item:
                        size = data['{}_size'.format(type_)]
                        order_amount.append(size)
                        order_sum += data['{}_price'.format(type_)] * size
                        
                        if order_sum >= btc_sum:
                            volume = order_sum / np.sum(order_amount)
                            avg_order_book[sai_symbol]['{}s'.format(type_)] = Decimal(volume)
                            
                            break
                
                return ExchangeResult(True, avg_order_book)
    
    async def compare_orderbook(self, other, symbol_list, default_btc=1):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="compare_orderbook", data=str(locals())))
        upbit_res, other_res = await asyncio.gather(
            self.get_curr_avg_orderbook(symbol_list, default_btc),
            other.get_curr_avg_orderbook(symbol_list, default_btc)
        )
        
        u_suc, u_orderbook, u_msg = upbit_res
        o_suc, o_orderbook, o_msg = other_res
        
        if u_suc and o_suc:
            m_to_s = dict()
            for currency_pair in symbol_list:
                m_ask = u_orderbook[currency_pair][Consts.ASKS]
                s_bid = o_orderbook[currency_pair][Consts.BIDS]
                m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask))
            
            s_to_m = dict()
            for currency_pair in symbol_list:
                m_bid = u_orderbook[currency_pair][Consts.BIDS]
                s_ask = o_orderbook[currency_pair][Consts.ASKS]
                s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask))
            result = (
                u_orderbook,
                o_orderbook,
                {Consts.PRIMARY_TO_SECONDARY: m_to_s, Consts.SECONDARY_TO_PRIMARY: s_to_m}
            )
            return ExchangeResult(True, result)
