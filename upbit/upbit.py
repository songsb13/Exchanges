import jwt
import time
import json
import aiohttp
import numpy as np
import asyncio
import requests
import threading
import datetime

from urllib.parse import urlencode
from Util.pyinstaller_patch import debugger

from Exchanges.settings import Consts, SaiOrderStatus, BaseTradeType
from Exchanges.messages import WarningMessage
from Exchanges.messages import DebugMessage

from Exchanges.upbit.setting import Urls, OrderStatus, DepositStatus, LocalConsts, WithdrawalStatus
from Exchanges.upbit.subscriber import UpbitSubscriber
from Exchanges.upbit.util import sai_to_upbit_symbol_converter, upbit_to_sai_symbol_converter, sai_to_upbit_trade_type_converter

from Exchanges.abstracts import BaseExchange
from Exchanges.objects import DataStore, ExchangeResult
from Exchanges.threads import CallbackThread

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

    def _get_results(self, response, path, extra, fn):
        try:
            res = json.loads(response)
        except:
            debugger.exception(DebugMessage.FATAL.format(name=self.name, fn=fn))
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

        raw_error = res.get('error', dict())

        if not raw_error:
            return ExchangeResult(True, res)
        else:
            raw_error_message = raw_error.get('message', None)
            if raw_error_message is None:
                error_message = WarningMessage.FAIL_RESPONSE_DETAILS.format(name=self.name, body=raw_error_message,
                                                                        path=path, parameter=extra)
            else:
                error_message = WarningMessage.MESSAGE_NOT_FOUND.format(name=self.name)

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

        authorization_token = self._sign_generator(payload)
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
            return ExchangeResult(False, message=WarningMessage.STEP_SIZE_NOT_FOUND.format(
                name=self.name,
                sai_symbol=sai_symbol,
            ))

    def _is_available_lot_size(self, symbol, krw_price, amount):
        market, coin = symbol.split('-')
        total_price = Decimal(krw_price * amount)

        minimum = LocalConsts.LOT_SIZES[market]['minimum']
        maximum = LocalConsts.LOT_SIZES[market]['maximum']
        if not minimum <= total_price <= maximum:
            msg = WarningMessage.WRONG_LOT_SIZE.format(
                name=self.name,
                market=market,
                minimum=minimum,
                maximum=maximum
            )
            return ExchangeResult(False, message=msg)

        return ExchangeResult(True)

    def _trading_validator_in_market(self, symbol, market_amount, trading_type):
        """
            validator for market
            Args:
                symbol: KRW, BTC
                amount: amount, Decimal
            Returns:
                True or False
                messages if getting false
        """
        market_current_price = 1

        if trading_type == BaseTradeType.SELL_MARKET:
            ticker_object = self.get_ticker(symbol)
            if not ticker_object.success:
                return ticker_object

            market_current_price = ticker_object.data['sai_price']

        lot_size_result = self._is_available_lot_size(symbol, market_current_price, market_amount)

        if not lot_size_result.success:
            return lot_size_result

        step_size_result = self._get_step_size(symbol, market_amount)

        return step_size_result

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

    def _sign_generator(self, *args):
        payload, *_ = args
        return 'Bearer {}'.format(jwt.encode(payload, self._secret, ).decode('utf8'))

    def set_subscriber(self):
        self._subscriber = UpbitSubscriber(self.data_store, self._lock_dic)

    def set_subscribe_candle(self, symbol):
        """
            subscribe candle.
            symbol: it can be list or string, [BTC-XRP, BTC-ETH] or 'BTC-XRP'
        """
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_candle", data=str(locals())))

        upbit_symbol_list = list(map(sai_to_upbit_symbol_converter, symbol)) if isinstance(symbol, list) \
            else sai_to_upbit_symbol_converter(symbol)

        callback_thread = CallbackThread(self._subscriber, upbit_symbol_list,
                                         self._subscriber.is_running, fn_name='upbit_set_subscribe_candle', context=self._lock_dic['candle'])

        callback_thread.start()

    def set_subscribe_orderbook(self, symbol):
        """
            subscribe orderbook.
            symbol: it can be list or string, [BTC-XRP, BTC-ETH] or 'BTC-XRP'
        """
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_orderbook", data=str(locals())))

        upbit_symbol_list = list(map(sai_to_upbit_symbol_converter, symbol)) if isinstance(symbol, list) \
            else sai_to_upbit_symbol_converter(symbol)
        callback_thread = CallbackThread(self._subscriber, upbit_symbol_list,
                                         self._subscriber.is_running, fn_name='upbit_set_subscribe_orderbook', context=self._lock_dic['orderbook'])

        callback_thread.start()

    def get_ticker(self, sai_symbol):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_ticker", data=str(locals())))
        symbol = sai_to_upbit_symbol_converter(sai_symbol)

        result = self._public_api(Urls.TICKER, {'markets': symbol})

        if result.success:
            ticker = Decimal(result.data[0]['trade_price']).quantize(Decimal(10) ** -8)
            result.data = {'sai_price': ticker}

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

    def get_deposit_history(self, coin, number):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_deposit_history", data=str(locals())))
        params = dict(
            currency=coin,
            state=DepositStatus.ACCEPTED
        )
        result = self._private_api(Consts.GET, Urls.GET_DEPOSIT_HISTORY, params)

        if result.success:
            latest_data = result.data[:number]
            result_dict = dict(
                sai_deposit_amount=latest_data['amount'],
                sai_coin=latest_data['currency']
            )
            result.data = result_dict

        return result

    def is_withdrawal_completed(self, coin, uuid):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="is_withdrawal_completed", data=str(locals())))
        params = dict(currency=coin, uuid=uuid, state=WithdrawalStatus.DONE)
        result = self._private_api(Consts.GET, Urls.GET_WITHDRAWAL_HISTORY, params)

        if result.success and result.data:
            for history_dict in result.data:
                history_id = history['uuid']
                if history_id == uuid:
                    sai_dict = dict(
                        sai_withdrawn_address=Consts.NOT_FOUND,
                        sai_withdrawn_amount=Decimal(history_dict['amount']).quantize(Decimal(10) ** -8),
                        sai_withdrawn_time=datetime.datetime.fromisoformat(history_dict['done_at']),
                        sai_coin=history_dict['currency'],
                        sai_network=Consts.NOT_FOUND,
                        sai_transaction_fee=Decimal(history_dict['fee']).quantize(Decimal(10) ** -8),
                        sai_transaction_id=history_dict['txid'],
                    )
                    result_dict = {**history_dict, **sai_dict}

                    return ExchangeResult(success=True, data=result_dict)
            else:
                message = WarningMessage.HAS_NO_WITHDRAW_ID.format(name=self.name, withdrawal_id=uuid)
                return ExchangeResult(success=False, message=message)
        else:
            return ExchangeResult(success=False, message=result.message)

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
                return ExchangeResult(True, data=result_list)
        else:
            return result

    def get_orderbook(self):
        with self._lock_dic['orderbook']:
            data_dic = self.data_store.orderbook_queue

            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, message=WarningMessage.ORDERBOOK_NOT_STORED.format(name=self.name),
                                      wait_time=1)
            return ExchangeResult(True, data_dic)

    def get_candle(self, sai_symbol):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_candle", data=str(locals())))
        with self._lock_dic['candle']:
            result = self.data_store.candle_queue.get(sai_symbol, None)
            if result is None:
                return ExchangeResult(False, message=WarningMessage.CANDLE_NOT_STORED.format(name=self.name), wait_time=1)
            return ExchangeResult(True, result)

    def get_trading_fee(self):
        dic_ = dict(KRW=Decimal(0.0005).quantize(Decimal(10) ** -8),
                    BTC=Decimal(0.0025).quantize(Decimal(10) ** -8),
                    USDT=Decimal(0.0025).quantize(Decimal(10) ** -8))
        return ExchangeResult(True, dic_)

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
    
    def buy(self, sai_symbol, trade_type, amount=None, price=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="buy", data=str(locals())))

        if not price:
            return ExchangeResult(False, message='')

        if BaseTradeType.BUY_LIMIT and not amount:
            return ExchangeResult(False, message='')

        upbit_trade_type = sai_to_upbit_trade_type_converter(trade_type)
        symbol = sai_to_upbit_symbol_converter(sai_symbol)

        default_parameters = {
            'market': symbol,
            'side': 'bid',
            'ord_type': upbit_trade_type
        }
        # market trading
        if trade_type == BaseTradeType.BUY_MARKET:
            trading_validation_result = self._trading_validator_in_market(symbol, amount, trade_type)
            if not trading_validation_result.success:
                return trading_validation_result
            stepped_price = trading_validation_result.data
            default_parameters.update(dict(price=stepped_price))
        else:
            trading_validation_result = self._trading_validator(symbol, amount)

            if not trading_validation_result.success:
                return trading_validation_result
            stepped_price = trading_validation_result.data
            default_parameters.update(dict(price=stepped_price, volume=amount))

        result = self._private_api(Consts.POST, Urls.ORDERS, default_parameters)

        if result.success:
            price = result.data['avg_price']
            amount = result.data['volume']
            result.data.update({
                'sai_average_price': Decimal(price).quantize(Decimal(10) ** - 8),
                'sai_amount': Decimal(amount).quantize(Decimal(10) ** - 8),
                'sai_order_id': result.data['uuid']

            })

        return result

    def sell(self, sai_symbol, trade_type, amount=None, price=None):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="sell", data=str(locals())))

        if amount is None:
            return ExchangeResult(False, message='')

        if BaseTradeType.SELL_LIMIT and not price:
            return ExchangeResult(False, message='')

        upbit_trade_type = sai_to_upbit_trade_type_converter(trade_type)
        symbol = sai_to_upbit_symbol_converter(sai_symbol)

        default_parameters = {
            'market': symbol,
            'side': 'ask',
            'volume': amount,
            'ord_type': upbit_trade_type
        }
        if trade_type == BaseTradeType.SELL_MARKET:
            trading_validation_result = self._trading_validator_in_market(symbol, amount, trade_type)
            if not trading_validation_result.success:
                return trading_validation_result
        else:
            trading_validation_result = self._trading_validator(symbol, amount)

            if not trading_validation_result.success:
                return trading_validation_result
            stepped_price = trading_validation_result.data
            default_parameters.update(dict(price=stepped_price))
        
        result = self._private_api(Consts.POST, Urls.ORDERS, default_parameters)

        if result.success:
            price = result.data['avg_price']
            amount = result.data['volume']
            result.data.update({
                'sai_average_price': Decimal(price).quantize(Decimal(10) ** - 8),
                'sai_amount': Decimal(amount).quantize(Decimal(10) ** - 8),
                'sai_order_id': result.data['uuid']
            })

        return result

    def base_to_alt(self, coin, alt_amount, from_exchange_trading_fee, to_exchange_transaction_fee):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="base_to_alt", data=str(locals())))
        alt_amount *= 1 - Decimal(from_exchange_trading_fee)
        alt_amount -= Decimal(to_exchange_transaction_fee[coin])
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

        authorization_token = self._sign_generator(payload)
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
        async with aiohttp.ClientSession() as s:
            url = Urls.Web.BASE + Urls.Web.TRANSACTION_FEE_PAGE
            rq = await s.get(url)

            result_text = await rq.text()
        raw_data = json.loads(result_text)

        success = raw_data.get('success', False)
        if not success:
            return ExchangeResult(False, '', message=WarningMessage.TRANSACTION_FAILED.format(name=self.name))

        data = json.loads(raw_data['data'])

        fees = dict()
        for each in data:
            coin = each['currency']
            fee = Decimal(each['withdrawFee']).quantize(Decimal(10) ** -6)
            fees.update({coin: fee})

        return ExchangeResult(True, fees)

    async def get_deposit_addrs(self, coin_list=None):
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

    async def get_balance(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_balance", data=str(locals())))
        result = await self._async_private_api(Consts.GET, Urls.ACCOUNT)

        if result.success:
            result.data = {bal['currency']: bal['balance'] for bal in result.data}

        return result

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1.0):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_curr_avg_orderbook", data=str(locals())))
        with self._lock_dic['orderbook']:
            data_dic = self.data_store.orderbook_queue
            
            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, message=WarningMessage.ORDERBOOK_NOT_STORED.format(name=self.name), wait_time=1)
            
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
    
    async def compare_orderbook(self, other_exchange, sai_symbol_list, default_btc=1.0):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="compare_orderbook", data=str(locals())))
        upbit_res, other_res = await asyncio.gather(
            self.get_curr_avg_orderbook(sai_symbol_list, default_btc),
            other_exchange.get_curr_avg_orderbook(sai_symbol_list, default_btc)
        )
        
        u_suc, u_orderbook, u_msg = upbit_res
        o_suc, o_orderbook, o_msg = other_res
        
        if u_suc and o_suc:
            m_to_s = dict()
            for currency_pair in sai_symbol_list:
                m_ask = u_orderbook[currency_pair][Consts.ASKS]
                s_bid = o_orderbook[currency_pair][Consts.BIDS]
                m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask))
            
            s_to_m = dict()
            for currency_pair in sai_symbol_list:
                m_bid = u_orderbook[currency_pair][Consts.BIDS]
                s_ask = o_orderbook[currency_pair][Consts.ASKS]
                s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask))
            result = (
                u_orderbook,
                o_orderbook,
                {Consts.PRIMARY_TO_SECONDARY: m_to_s, Consts.SECONDARY_TO_PRIMARY: s_to_m}
            )
            return ExchangeResult(True, result)
