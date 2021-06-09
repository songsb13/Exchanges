import sys
import hmac
import hashlib
import requests
import json
import websocket
import logging
from threading import Thread
from urllib.parse import urlencode
from datetime import datetime
from decimal import *
import asyncio
import time
import math
import aiohttp


binance_logger = logging.getLogger(__name__)
binance_logger.setLevel(logging.DEBUG)

f_hdlr = logging.FileHandler('binance_logger.log')
s_hdlr = logging.StreamHandler()

binance_logger.addHandler(f_hdlr)
binance_logger.addHandler(s_hdlr)


class Binance:
    def __init__(self,key,secret):
        self._endpoint = 'https://api.binance.com'
        self._key = key
        self._secret = secret
        while True:
            self.exchange_info = self.get_exchange_info()

            if self.exchange_info[0]: # exchange_info는 무조건 성공해야 하는 부분임.(내부)
                break

            time.sleep(1)
        #self._plus = 1
        #self._nonce = 0

    def servertime(self):
        stat = self.public_api('/api/v1/time')

        return stat['serverTime']

    def encrypto(self, params):
        if params is None:
            params = {}

        query = urlencode(sorted(params.items()))
        _nonce = self.servertime()

        query += "&timestamp={}".format(_nonce)
        sign = hmac.new(self._secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()

        query += "&signature={}".format(sign)

        return query

    def private_api(self,method, path, params=None):
        if params is None:
            params = {}
        try:
            query = self.encrypto(params)

            req = requests.request(method,self._endpoint + path,params =query,headers={"X-MBX-APIKEY": self._key})
            rps = req.json()

        except Exception as e:
            rps = {'success': False, 'msg': str(e)}

        return rps

    def public_api(self, path, params=None):
        if params is None:
            params = {}
        try:
            req = requests.get(self._endpoint + path ,params = params)
            rps = req.json()
        except Exception as e:
            rps = {'success': False, 'msg': str(e)}

        return rps

    def get_exchange_info(self):  # API에서 제공하는 서비스 리턴
        stat = self.public_api('/api/v1/exchangeInfo')

        if 'msg' in stat:
            binance_logger.debug('exchange_info에서 에러 발생 [{}]'.format(stat))
            return False,'',stat['msg'],1

        #_av_coin = []
        _step_size = {}
        for i in stat['symbols']:
            flag_symbol = i['symbol'][-3:] # BTC ETH와 같은 기축통화
            if 'BTC' in flag_symbol: # 기준이 BTC인경우
                coin_name = flag_symbol + '_' + i['symbol'][:-3] # BNBBTC --> BTC_BNB 이런식으로 변경
                #_av_coin.append(coin_name)
                _step_size.update({coin_name:i['filters'][1]['stepSize']})

        return True,_step_size,'Success',0# StepSize는 내부에서 쓰이기때문에 True등을 리턴하지않는다.

    def get_step_size(self,symbol):
        if symbol == 'BTC_BCH':
            symbol = 'BTC_BCC'
        step_size = self.exchange_info[1][symbol]

        index = Decimal(step_size).normalize()

        return True,index,'Success',0

    def get_precision(self, pair):
        if pair == 'BTC_BCH':
            pair = 'BTC_BCC'
        if pair in self.exchange_info[1]:
            return True, (-8, int(math.log10(float(self.exchange_info[1][pair])))), '', 0
        else:
            return False, '', '[Binance] {} 호가 정보가 없습니다.'.format(pair), 60

    def get_available_coin(self):  # API에서 제공하는 서비스 리턴
        coin = self.exchange_info[1].keys()
        _list = []
        for _av in coin:
            _list.append(_av)

        return True,_list,'Success',0

    def buy(self,coin,amount):
        binance_logger.info('### buy [{}],[{}] 입력됨'.format(coin, amount))
        coin = coin.split('_')
        if coin[1] == 'BCH':
            coin[1] = 'BCC'

        coin = coin[1] + coin[0]
        params = {
                    'symbol':coin,
                    'side':'buy',#(coin)buy,(coin)sell
                    'quantity': '{}'.format(amount).strip(),
                    'type':'MARKET'
                  }

        #binance_logger.debug("params = {}.".format(params))

        rq = self.private_api('POST','/api/v3/order',params)

        if 'msg' in rq:
            binance_logger.debug('buy 에러 발생 [{}]'.format(rq))

            return False,'',rq['msg'],1

        return True,rq,'Success',0

    def sell(self,coin,amount):
        binance_logger.info('### sell [{}],[{}] 입력됨'.format(coin,amount))

        symbol = coin.split('_')
        if symbol[1] == 'BCH':
            symbol[1] = 'BCC'

        coin = symbol[1] + symbol[0]

        params = {
                    'symbol':coin,
                    'side':'sell',#(symbol)buy,(symbol)sell
                    'quantity':'{}'.format(amount).strip(),
                    'type':'MARKET'
                  }
        #binance_logger.debug("params = {}.".format(params))

        rq = self.private_api('POST','/api/v3/order',params)

        if 'msg' in rq:
            binance_logger.debug('sell 에러 발생 [{}]'.format(rq))

            return False,'',rq['msg'],1

        return True,rq,'Success',0

    def fee_count(self):
        return 1

    def bnc_btm_quantizer(self,symbol):
        binance_qtz = self.get_step_size(symbol)[1]
        return Decimal(10) ** -4 if binance_qtz < Decimal(10) ** -4 else binance_qtz

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        # btc sell alt buy
        # alt_amount = Decimal(alt_amount)

        success, result, error, ts = self.buy(currency_pair,alt_amount)

        coin = currency_pair.split('_')[1]
        # 보내야하는 alt의 양 계산함.
        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[coin])
        alt_amount = alt_amount.quantize(self.bnc_btm_quantizer(currency_pair), rounding=ROUND_DOWN)

        if not success:
            binance_logger.info(error)
            time.sleep(ts)
            return False, '', error, ts

        # return success
        return True, alt_amount, '', 0

    def alt_to_base(self,currency_pair,btc_amount,alt_amount):
        # coin = currency_pair.split('_')[1]

        while True:
            success, result, error, ts = self.sell(currency_pair, alt_amount)

            if success:
                break

            binance_logger.info(error)
            time.sleep(ts)

    def get_ticker(self):
        rq = self.public_api('/api/v1/ticker/24hr')

        return rq

    def withdraw(self,coin,amount,to_address,payment_id = None):
        binance_logger.info('withdraw - [{}][{}][{}][{}] 받았음.'.format(coin, amount, to_address, payment_id))

        if coin == 'BCH':
            coin = 'BCC'
        params = {
                    'asset':coin,
                    'address':to_address,
                    'amount':'{}'.format(amount),
                    'name': 'SAICDiffTrader'
                }

        if payment_id:
            tag_dic = {'addressTag':payment_id}
            params.update(tag_dic)

        #binance_logger.debug("params = {}.".format(params))


        rq = self.private_api('POST','/wapi/v3/withdraw.html',params)

        if rq['msg'].lower() != 'success':
            binance_logger.debug('withdraw 에러 발생 [{}]'.format(rq))

            return False,'',rq['msg'],1

        return True,rq,'Success',0

    async def async_private_api(self,s, method, path, params=None):
        if params is None:
            params = {}

        query = self.encrypto(params)

        if method == 'GET':
            async with s.get(self._endpoint + path, params=query) as rps:
                rps = await rps.text()
        else:
            async with s.post(self._endpoint + path, data=query) as rps:
                rps = await rps.text()

        # try:
        #     rps = await req.text()
        # except Exception as e:
        #     rps = {'success': False , 'msg': str(e)}

        return json.loads(rps)

    async def async_public_api(self, path, params=None):
        if params is None:
            params = {}

        async with aiohttp.ClientSession() as s:
            req = await s.get(self._endpoint + path ,params = params)

        try:
            rps = await req.text()
        except Exception as e:
            rps = {'success': False, 'msg': str(e)}

        return json.loads(rps)

    async def get_deposit_addrs(self):
        rq_dic = {}

        av_data = self.get_available_coin()

        # if not av_data: # get_available_coin의 성공여부 확인
        #     return av_data #return False,'',msg,1

        coin_lists = av_data[1]
        coin_lists.append('BTC_BTC')
        try:
            async with aiohttp.ClientSession(headers={"X-MBX-APIKEY": self._key}) as s:
                for coin in coin_lists:
                    coin_sp = coin.split('_')[1]
                    if coin_sp == 'BCH':
                        coin_sp = 'BCC'

                    rq = await self.async_private_api(s, 'GET','/wapi/v3/depositAddress.html',{'asset':coin_sp})
                    # binance_logger.debug('get_deposit_addrs 에러 발생 [{}]'.format(rq))
                    # binance_logger.info('출금주소를 가져오는중 에러가 발생해 1분뒤 재시도합니다.')
                    # time.sleep(60)

                    if rq['success'] == False:
                        binance_logger.debug('점검중인 코인[{}]'.format(coin))

                        continue

                    rq_dic[coin_sp] = rq['address']

                    try:
                        tag = rq['addressTag']
                    except:
                        tag = ''

                    if not tag == '':
                        rq_dic[coin_sp+'TAG'] = tag

            return True, rq_dic, 'Success', 0
        except Exception as e:
            return False, '', 'Fail![{}]'.format(str(e)), 1

    async def get_avg_price(self,coins): # 내거래 평균매수가
        _amount_price_list = []
        _return_values = []

        for coin in coins:
            total_price = 0
            _bid_count = 0
            total_amount = 0
            while True:
                history = await self.async_public_api('/api/v3/allOrders',{'symbol':coin})

                if not 'msg' in history:
                    binance_logger.debug('get_avg_price 에러 발생 [{}]'.format(history))
                    break

            history.reverse()
            for _data in history:
                side = _data['side']
                n_price = float(_data['price'])
                price = Decimal(n_price - (n_price *0.1)).quantize(Decimal(10) ** -6)
                amount = Decimal(_data['origQty']).quantize(Decimal(10) ** -6)
                if side == 'BUY':
                    _amount_price_list.append({
                        '_price': price ,
                        '_amount': amount
                    })
                    total_price += price
                    total_amount += amount
                    _bid_count += 1
                else:
                    total_amount -= amount
                if total_amount <= 0:
                    _bid_count -=1
                    total_price = 0
                    _amount_price_list.pop(0)

            _values = {coin: {
                'avg_price': total_price/_bid_count,
                'coin_num': total_amount
            }}
            _return_values.append(_values)

        return True, _return_values, 'Success', 1

    async def get_trading_fee(self): #Binance는 trade_fee가 0.1로 되어있음.
        return True, 0.001, '', 0

    async def get_transaction_fee(self):
        _fee_info = {}
        try:
            async with aiohttp.ClientSession() as s:
                rq = await s.get('https://www.binance.com/assetWithdraw/getAllAsset.html')
                _data_list = await rq.text()
                _data_list = json.loads(_data_list)

            if _data_list == []:
                binance_logger.debug('get_transaction_fee 에러 발생 [{}]'.format(rq))

                return False, '','Request fail to all asset', 60

            try:
                for f in _data_list:
                    if f['assetCode'] == 'BCC':
                        f['assetCode'] = 'BCH'
                    _fee_info[f['assetCode']] = Decimal(f['transactionFee']).quantize(Decimal(10)**-8)  # _fee_info[BNB] = 어쭈구
            except:
                pass
        except Exception as e:
            return False, '', str(e), 60

        return True,_fee_info,'Success',0

    async def balance(self):
        # async with aiohttp.ClientSession(headers={"X-MBX-APIKEY": self._key}) as s:
        #     rq = await self.async_private_api(s, 'GET','/api/v3/account')
        rq = self.private_api('GET', '/api/v3/account')

        if 'msg' in rq:
            return False, '', rq['msg'], 3

        balance = {}
        for _info in rq['balances']:
            if _info['asset'] == 'BCC':
                _info['asset'] = 'BCH'

            if float(_info['free']) > 0:
                balance[_info['asset'].upper()] = float(_info['free']) # asset-> 코인이름 free -> 거래가능한 코인수

        return True,balance,'Success',0

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):  # 상위 평균매도/매수가 구함
        avg_order_book = {}
        try:
            for _currency_pair in coin_list:
                if _currency_pair == 'BTC_BTC':
                    continue
                convt_name = _currency_pair.split('_')
                coin = convt_name[1]+convt_name[0]

                avg_order_book[_currency_pair] = {}
                _book = await self.async_public_api('/api/v1/depth',{'symbol': coin})
                for _type in ['asks', 'bids']:
                    _order_amount = 0
                    _order_sum = 0
                    _info = _book[_type]
                    for _data in _info:
                        _order_amount += Decimal(_data[1])  # 0 - price 1 - qty
                        _order_sum += (Decimal(_data[0]) * Decimal(_data[1])).quantize(Decimal(10) ** -8)
                        if _order_sum >= Decimal(btc_sum):
                            _v = ((_order_sum / _order_amount).quantize(Decimal(10) ** -8))
                            avg_order_book[_currency_pair][_type] = _v
                            break
            return True,avg_order_book,'',0

        except Exception as e:
             return False,'','get_curr_avg_orderbook_error[{}]'.format(str(e)),1

    async def compare_orderbook(self, other, coins=[], default_btc=1):
        # currency_pairs = ['BTC_'+ coin for coin in coins if coin !="BTC"]
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            binance_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(coins, default_btc),
                                                                other.get_curr_avg_orderbook(coins, default_btc))

            success, binance_avg_orderbook, err, st = binance_result
            success2, other_avg_orderbook, err2, st2 = other_result

            if 'BTC' in coins:
                coins.remove('BTC')

            if success and success2:
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

                ret = (binance_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m})

                return True, ret, '', 0
            else:
                future = asyncio.sleep(st) if st > st2 else asyncio.sleep(st2)
                await future
                continue
        else:
            if not err:
                return False, '', err2, st2
            else:
                return False, '', err, st
