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

from Exchanges.settings import Consts

from Exchanges.upbit.setting import Urls
from Exchanges.upbit.subscriber import UpbitSubscriber
from Exchanges.upbit.util import sai_to_upbit_symbol_converter, upbit_to_sai_symbol_converter

from Exchanges.abstracts import BaseExchange
from Exchanges.objects import DataStore, ExchangeResult

import decimal

decimal.getcontext().prec = 8


class BaseUpbit(BaseExchange):
    def __init__(self, key, secret):
        self._key = key
        self._secret = secret
        self.data_store = DataStore()
        
        self._lock_dic = dict(orderbook=threading.Lock(), candle=threading.Lock())
        
        self._subscriber = UpbitSubscriber(self.data_store, self._lock_dic)
    
    def start_socket_thread(self):
        self.subscribe_thread = threading.Thread(target=self._subscriber.run_forever, daemon=True)
        self.subscribe_thread.start()

    def _public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        
        url = Urls.BASE + path
        rq = requests.get(url, json=extra)
        try:
            res = rq.json()
            
            if 'error' in res:
                error_msg = res.get('error', dict()).get('message', 'Fail, but message is not found.')
                return ExchangeResult(False, '', error_msg)
            
            else:
                return ExchangeResult(True, res)
        
        except Exception as ex:
            return False, '', 'Error [{}]'.format(ex)
    
    def _private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }
        
        if extra is not None:
            payload.update({'query': urlencode(extra)})
        
        header = self.get_jwt_token(payload)
        
        url = Urls.BASE + path
        rq = requests.post(url, header=header, data=extra)

        try:
            res = rq.json()
    
            if 'error' in res:
                error_msg = res.get('error', dict()).get('message', 'Fail, but message is not found.')
                return ExchangeResult(False, '', error_msg)
    
            else:
                return ExchangeResult(True, res)

        except Exception as ex:
            return ExchangeResult(False, '', 'Error [{}]'.format(ex))

    def fee_count(self):
        return 1
    
    def get_jwt_token(self, payload):
        return 'Bearer {}'.format(jwt.encode(payload, self._secret, ).decode('utf8'))
    
    def get_ticker(self, market):
        return self._public_api(Urls.TICKER, market)
    
    def currencies(self):
        # using get_currencies, service_currencies
        return self._public_api(Urls.CURRENCY)
    
    def get_currencies(self, currencies):
        res = list()
        return [res.append(data['market']) for data in currencies if not currencies['market'] in res]
    
    def get_candle(self, coin, unit, count):
        with self._lock_dic['candle']:
            self._subscriber.add_candle_symbol_set(coin)
            
            if not self.data_store.candle_queue:
                return ExchangeResult(False, '', 'candle data is not yet stored', 1)
            
            result_dict = self.data_store.candle_queue
            
            return ExchangeResult(True, result_dict, '', 0)
        
    def service_currencies(self, currencies):
        # using deposit_addrs
        res = list()
        return [res.append(data.split('-')[1]) for data in currencies if currencies['market'].split('-')[1] not in res]
    
    def get_order_history(self, uuid):
        return self._private_api(Consts.GET, Urls.ORDER, {'uuid': uuid})
    
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
        order_type = 'price' if price is None else 'limit'
        
        amount, price = map(str, (amount, price))
        
        params = {
            'market': coin,
            'side': 'bid',
            'volume': amount,
            'price': price,
            'ord_type': order_type
        }
        
        return self._private_api(Consts.POST, Urls.ORDER, params)
    
    def sell(self, coin, amount, price=None):
        order_type = 'market' if price is None else 'limit'

        amount, price = map(str, (amount, price))
        
        params = {
            'market': coin,
            'side': 'ask',
            'volume': amount,
            'price': price,
            'ord_type': order_type
        }
        
        return self._private_api(Consts.POST, Urls.ORDER, params)
    
    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        alt_amount *= 1 - decimal.Decimal(td_fee)
        alt_amount -= decimal.Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount
        
        return ExchangeResult(True, alt_amount)
    
    async def async_public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        try:
            async with aiohttp.ClientSession() as s:
                url = Urls.BASE + path
                rq = await s.get(url, json=extra)
                
                res = json.loads(await rq.text())
                
                if 'error' in res:
                    error_msg = res.get('error', dict()).get('message',
                                                             'Fail, but message is not found.')
    
                    return ExchangeResult(False, '', error_msg)
                
                else:
                    return True, res, ''
        except Exception as ex:
            return ExchangeResult(False, '', 'Error [{}]'.format(ex))
    
    async def async_private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }
        
        if extra is not None:
            payload.update({'query': urlencode(extra)})
        header = self.get_jwt_token(payload)
        try:
            async with aiohttp.ClientSession() as s:
                url = Urls.BASE + path
                rq = await s.post(url, headers=header, data=extra)
        
                res = json.loads(await rq.text())
        
                if 'error' in res:
                    error_msg = res.get('error', dict()).get('message',
                                                             'Fail, but message is not found.')
    
                    return ExchangeResult(False, '', error_msg)
        
                else:
                    return ExchangeResult(True, res)
        except Exception as ex:
            return ExchangeResult(False, '', 'Error [{}]'.format(ex))
    
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
            self._subscriber.add_orderbook_symbol_set(coin_list)
            data_dic = self.data_store.orderbook_queue
            
            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, '', 'orderbook data is not yet stored')
            
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
    
    async def compare_orderbook(self, other, coins, default_btc=1):
        upbit_res, other_res = await asyncio.gather(
            self.get_curr_avg_orderbook(coins, default_btc),
            other.get_curr_avg_orderbook(coins, default_btc)
        )
        
        u_suc, u_orderbook, u_msg = upbit_res
        o_suc, o_orderbook, o_msg = other_res
        
        if u_suc and o_suc:
            m_to_s = dict()
            for currency_pair in coins:
                m_ask = u_orderbook[currency_pair]['asks']
                s_bid = o_orderbook[currency_pair]['bids']
                m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask))
            
            s_to_m = dict()
            for currency_pair in coins:
                m_bid = u_orderbook[currency_pair]['bids']
                s_ask = o_orderbook[currency_pair]['asks']
                s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask))
            
            res = u_orderbook, o_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m}
            
            return ExchangeResult(True, res)

