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

from Exchanges.upbit.setting import Urls, OrderStatus
from Exchanges.upbit.subscriber import UpbitSubscriber
from Exchanges.upbit.util import sai_to_upbit_symbol_converter, upbit_to_sai_symbol_converter

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
        
        self._subscriber = UpbitSubscriber(self.data_store, self._lock_dic)

    def _public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        
        url = Urls.BASE + path
        rq = requests.get(url, params=extra)
        try:
            res = rq.json()
            
            if 'error' in res:
                error_msg = res.get('error', dict()).get('message', WarningMsg.MESSAGE_NOT_FOUND.format(name=self.name))
                return ExchangeResult(False, message=error_msg, wait_time=1)
            
            else:
                return ExchangeResult(True, res)
        
        except:
            debugger.exception('FATAL: Upbit, _public_api')
            return ExchangeResult(False, message=WarningMsg.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    def _private_api(self, method, path, extra=None):
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

        try:
            res = rq.json()
    
            if 'error' in res:
                error_msg = res.get('error', dict()).get('message', WarningMsg.MESSAGE_NOT_FOUND.format(name=self.name))
                return ExchangeResult(False, message=error_msg, wait_time=1)
    
            else:
                return ExchangeResult(True, res)

        except:
            debugger.exception('FATAL: Upbit, _private_api')
            return ExchangeResult(False, message=WarningMsg.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    def fee_count(self):
        return 1
    
    def get_jwt_token(self, payload):
        return 'Bearer {}'.format(jwt.encode(payload, self._secret, ).decode('utf8'))

    def get_ticker(self, symbol):
        symbol = sai_to_upbit_symbol_converter(symbol)

        result = self._public_api(Urls.TICKER, {'markets': symbol})

        if result.success:
            result.data = {'sai_price': result.data[0]['trade_price']}

        return result

    def get_order_history(self, uuid, additional_parameter):
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

    def get_available_symbols(self):
        result = self._public_api(Urls.CURRENCY)

        if result.success:
            result_list = list()
            for data in result.data:
                symbol = data.get('market')
                if symbol:
                    converted = upbit_to_sai_symbol_converter(symbol)
                    result_list.append(converted.replace('-', '_'))
            else:
                return result_list

    def set_subscribe_candle(self, symbol):
        """
            subscribe candle.
            symbol: it can be list or string, [BTC-XRP, BTC-ETH] or 'BTC-XRP'
        """
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
        coin = list(map(sai_to_upbit_symbol_converter, symbol)) if isinstance(symbol, list) \
            else sai_to_upbit_symbol_converter(symbol)
        with self._lock_dic['orderbook']:
            self._subscriber.subscribe_orderbook(coin)

        return True

    def get_candle(self, coin):
        with self._lock_dic['candle']:
            result = self.data_store.candle_queue.get(coin, None)
            if result is None:
                return ExchangeResult(False, message=WarningMsg.CANDLE_NOT_STORED.format(name=self.name), wait_time=1)
            return ExchangeResult(True, result)

    def service_currencies(self, currencies):
        # using deposit_addrs
        res = list()
        return [res.append(data.split('-')[1]) for data in currencies if currencies['market'].split('-')[1] not in res]
    
    def withdraw(self, coin, amount, to_address, payment_id=None):
        params = {
            'currency': coin,
            'address': to_address,
            'amount': str(amount),
        }
        
        if payment_id:
            params.update({'secondary_address': payment_id})
        
        return self._private_api(Consts.POST, Urls.WITHDRAW, params)
    
    def buy(self, coin, amount, price=None):
        order_type = Consts.MARKET if price is not None else Consts.LIMIT
        amount, price = map(str, (amount, price))
        
        params = {
            'market': coin,
            'side': 'bid',
            'volume': amount,
            'price': price,
            'ord_type': order_type
        }
        
        return self._private_api(Consts.POST, Urls.ORDERS, params)
    
    def sell(self, coin, amount, price=None):
        order_type = Consts.MARKET if price is not None else Consts.LIMIT

        amount, price = map(str, (amount, price))
        
        params = {
            'market': coin,
            'side': 'ask',
            'volume': amount,
            'price': price,
            'ord_type': order_type
        }
        
        return self._private_api(Consts.POST, Urls.ORDERS, params)
    
    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        alt_amount *= 1 - decimal.Decimal(td_fee)
        alt_amount -= decimal.Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount
        
        return ExchangeResult(True, alt_amount)

    def check_order(self, data, profit_object):
        return data
        # uuid = parameter['uuid']
        # result = self._private_api(Consts.GET, Urls.ORDER, dict(uuid=uuid))

    async def async_public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        try:
            async with aiohttp.ClientSession() as s:
                url = Urls.BASE + path
                rq = await s.get(url, params=extra)
                
                res = json.loads(await rq.text())
                
                if 'error' in res:
                    error_msg = res.get('error', dict()).get('message',
                                                             WarningMsg.MESSAGE_NOT_FOUND.format(name=self.name))
    
                    return ExchangeResult(False, message=error_msg, wait_time=1)
                
                else:
                    return ExchangeResult(True, res)
        except:
            debugger.exception('FATAL: Upbit, _async_public_api')
            return ExchangeResult(False, message=WarningMsg.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    async def async_private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }
        
        if extra is not None:
            payload.update({'query': urlencode(extra)})

        authorization_token = self.get_jwt_token(payload)
        header = {'Authorization': authorization_token}
        url = Urls.BASE + path

        try:
            async with aiohttp.ClientSession() as s:
                if method == Consts.GET:
                    rq = await s.get(url, headers=header, data=extra)
                else:
                    rq = await s.post(url, headers=header, data=extra)
        
                res = json.loads(await rq.text())
        
                if 'error' in res:
                    error_msg = res.get('error', dict()).get('message',
                                                             WarningMsg.MESSAGE_NOT_FOUND.format(name=self.name))
    
                    return ExchangeResult(False, message=error_msg, wait_time=1)
        
                else:
                    return ExchangeResult(True, res)
        except:
            debugger.exception('FATAL: Upbit, async_private_api')
            return ExchangeResult(False, message=WarningMsg.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

    async def get_transaction_fee(self):
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

    async def get_deposit_addrs(self, coin_list=None):
        return self.async_public_api(Urls.DEPOSIT_ADDRESS)
    
    async def get_balance(self):
        return self._private_api(Consts.GET, Urls.ACCOUNT)
    
    async def get_detail_balance(self, data):
        # bal = self.get_balance()
        return {bal['currency']: bal['balance'] for bal in data}
    
    async def get_orderbook(self, market):
        return self.async_public_api(Urls.ORDERBOOK, {'markets': market})
    
    async def get_btc_orderbook(self, btc_sum):
        return await self.get_orderbook('KRW-BTC')
    
    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
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
                            avg_order_book[sai_symbol]['{}s'.format(type_)] = decimal.Decimal(volume)
                            
                            break
                
                return ExchangeResult(True, avg_order_book)
    
    async def compare_orderbook(self, other, symbol_list, default_btc=1):
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
