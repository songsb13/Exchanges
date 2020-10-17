import jwt
import requests
import time
import json
import aiohttp
import numpy as np
import asyncio
import threading

from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlencode
from Util.pyinstaller_patch import *

from Exchanges.base_exchange import BaseExchange, ExchangeResult
from Exchanges.Upbit.subscriber import UpbitSubscriber
from Exchanges.base_exchange import DataStore


class BaseUpbit(BaseExchange):
    def __init__(self, key, secret, candle_time, coin_list):
        self._base_url = 'https://api.upbit.com/v1'
        self._key = key
        self._secret = secret
        self.data_store = DataStore()
        
        self._candle_time = candle_time
        self._coin_list = coin_list
        self._lock_dic = dict(orderbook=threading.Lock(), candle=threading.Lock())
        
        self._subscriber = UpbitSubscriber(self.data_store, self._lock_dic)
        
        self._connect_to_subscriber()
        
    def _sai_to_upbit_symbol_converter(self, pair):
        return pair.replace('_', '-')
    
    def _upbit_to_sai_symbol_converter(self, pair):
        return pair.replace('-', '_')
    
    def _connect_to_subscriber(self):
        for _ in range(3):
            debugger.debug('connecting to subscriber..')
            try:
                self._websocket_orderbook_settings()
                self._websocket_candle_settings()
                debugger.debug('connected.')
                break
            except Exception as ex:
                print(ex)
            time.sleep(1)
        else:
            debugger.exception('Fail to set websocket settings')
            raise
            
    def _websocket_candle_settings(self):
        if not self._subscriber.candle_symbol_set:
            pairs = [self._sai_to_upbit_symbol_converter(pair) for pair in self._coin_list]
            setattr(self._subscriber, 'candle_symbol_set', pairs)

        if self._subscriber.subscribe_set.get('candle', None) is None or not self._subscriber.subscribe_thread.isAlive():
            self._subscriber.subscribe_candle()

    def _websocket_orderbook_settings(self):
        if not self._subscriber.orderbook_symbol_set:
            pairs = [self._sai_to_upbit_symbol_converter(pair) for pair in self._coin_list]
            setattr(self._subscriber, 'orderbook_symbol_set', pairs)
    
        if self._subscriber.subscribe_set.get('orderbook', None) is None or not self._subscriber.subscribe_thread.isAlive():
            self._subscriber.subscribe_orderbook()

    def _public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        
        path = self._base_url + path
        rq = requests.get(path, json=extra)
        try:
            res = rq.json()
            
            if 'error' in res:
                return ExchangeResult(False, '', res['error']['message'])
            
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
        
        path = '/'.join([self._base_url, path])
        rq = requests.post(path, header=header, data=extra)

        try:
            res = rq.json()
    
            if 'error' in res:
                return ExchangeResult(False, '', res['error']['message'])
    
            else:
                return ExchangeResult(True, res)

        except Exception as ex:
            return ExchangeResult(False, '', 'Error [{}]'.format(ex))

    def fee_count(self):
        return 1
    
    def get_jwt_token(self, payload):
        return 'Bearer {}'.format(jwt.encode(payload, self._secret, ).decode('utf8'))
    
    def get_ticker(self, market):
        return self._public_api('/ticker', market)
    
    def currencies(self):
        # using get_currencies, service_currencies
        return self._public_api('/market/all')
    
    def get_currencies(self, currencies):
        res = list()
        return [res.append(data['market']) for data in currencies if not currencies['market'] in res]
    
    def get_candle(self):
        if not self.data_store.candle_queue:
            return ExchangeResult(False, '', 'candle data is not yet stored', 1)
        
        result_dict = self.data_store.candle_queue
        
        return ExchangeResult(True, result_dict, '', 0)
        
    def service_currencies(self, currencies):
        # using deposit_addrs
        res = list()
        return [res.append(data.split('-')[1]) for data in currencies if currencies['market'].split('-')[1] not in res]
    
    def get_order_history(self, uuid):
        return self._private_api('get', '/order', {'uuid': uuid})
    
    def withdraw(self, coin, amount, to_address, payment_id=None):
        params = {
            'currency': coin,
            'address': to_address,
            'amount': str(amount),
        }
        
        if payment_id:
            params.update({'secondary_address': payment_id})
        
        return self._private_api('post', '/withdraws/coin', params)
    
    def buy(self, coin, amount, price=None):
        amount, price = map(str, (amount, price * 1.05))
        
        params = {
            'market': coin,
            'side': 'bid',
            'volume': amount,
            'price': price,
            'ord_type': 'limit'
        }
        
        return self._private_api('POST', '/orders', params)
    
    def sell(self, coin, amount, price=None):
        amount, price = map(str, (amount, price * 0.95))
        
        params = {
            'market': coin,
            'side': 'ask',
            'volume': amount,
            'price': price,
            'ord_type': 'limit'
        }
        
        return self._private_api('POST', '/orders', params)
    
    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)
        
        return ExchangeResult(True, alt_amount)
    
    # def alt_to_base(self, currency_pair, btc_amount, alt_amount):
    #     # after self.sell()
    #     if suc:
    #         upbit_logger.info('AltToBase 성공')
    #
    #         return True, '', data, 0
    #
    #     else:
    #         upbit_logger.info(msg)
    #
    #         if '부족합니다.' in msg:
    #             alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
    #             continue
    
    async def async_public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        try:
            async with aiohttp.ClientSession() as s:
                path = self._base_url + path
                rq = await s.get(path, json=extra)
                
                res = json.loads(await rq.text())
                
                if 'error' in res:
                    return ExchangeResult(False, '', res['error']['message'])
                
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
                path = self._base_url + path
                rq = await s.post(path, headers=header, data=extra)
        
                res = json.loads(await rq.text())
        
                if 'error' in res:
                    return ExchangeResult(False, '', res['error']['message'])
        
                else:
                    return ExchangeResult(True, res)
        except Exception as ex:
            return ExchangeResult(False, '', 'Error [{}]'.format(ex))
    
    async def get_deposit_addrs(self, coin_list=None):
        return self.async_public_api('/v1/deposits/coin_addresses')
    
    async def get_balance(self):
        return self._private_api('get', '/accounts')
    
    async def get_detail_balance(self, data):
        # bal = self.get_balance()
        return {bal['currency']: bal['balance'] for bal in data}
    
    async def get_orderbook(self, market):
        return self.async_public_api('/orderbook', {'markets': market})
    
    async def get_btc_orderbook(self, btc_sum):
        return await self.get_orderbook('KRW-BTC')
    
    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        with self._lock_dic['orderbook']:
            data_dic = self.data_store.orderbook_queue
            
            if not self.data_store.orderbook_queue:
                return ExchangeResult(False, '', 'orderbook data is not yet stored')
            
            avg_order_book = dict()
            for pair, item in data_dic.items():
                sai_symbol = self._upbit_to_sai_symbol_converter(pair)
                avg_order_book[sai_symbol] = dict()
                
                for type_ in ['ask', 'bid']:
                    order_amount, order_sum = list(), 0
                    for data in item:
                        size = data['{}_size'.format(type_)]
                        order_amount.append(size)
                        order_sum += data['{}_price'.format(type_)] * size
                        
                        if order_sum >= btc_sum:
                            volume = order_sum / np.sum(order_amount)
                            avg_order_book[sai_symbol]['{}s'.format(type_)] = Decimal(volume).quantize(Decimal(10) ** -8)
                            
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
                m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))
            
            s_to_m = dict()
            for currency_pair in coins:
                m_bid = u_orderbook[currency_pair]['bids']
                s_ask = o_orderbook[currency_pair]['asks']
                s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))
            
            res = u_orderbook, o_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m}
            
            return ExchangeResult(True, res)

