import requests
import json
from decimal import Decimal
import logging
import sys
import os
import asyncio
import configparser
from decimal import ROUND_DOWN
import time

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

# if 'pydevd' not in sys.modules:
#     from .models import korbitAvg

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

f_hdlr = logging.FileHandler('logger.log')
s_hdlr = logging.StreamHandler()

logger.addHandler(f_hdlr)
logger.addHandler(s_hdlr)

cfg = configparser.ConfigParser()
cfg.read('./Settings.ini')


class Korbit:
    def __init__(self,client_id,client_secret,username,secret):
        self.endpoint = 'https://api.korbit.co.kr'
        self._token = {}
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._secret = secret

        while True:
            token = self.get_token()

            try: # 토큰획득에 실패할경우 Error라는 dic이 생성된다.
                logger.debug(token['error'])
                logger.info('토큰 획득에 실패하여 10초뒤 재검증합니다.')
                time.sleep(10)
            except:
                logger.info('Token 획득.')
                break
    def error_check(self,stat,_time):
        suc = False

        if 'error' in stat :
            msg = stat['error']
            stat = ''

        else:
            suc = True
            msg = ''
            _time = 0
        # elif not stat['status'] == 'success':
        #     msg = stat['status']
        #     stat = ''

        return [suc,stat,msg,_time]

    def public_api(self, method, cmd, param = {}):
        while True:
            try:
                rt = requests.request(method, self.endpoint + cmd, params = param, headers = self.header())

                logger.debug('Korbit-Public API[{}, {}]- {} --{}'.format(method, cmd, rt.status_code, rt.text))

                return rt.json()

            except Exception as e: #
                logger.debug('Korbit-Public API Request Error')
                logger.debug(e)

                time.sleep(3)

    def private_api(self, method, cmd, param = {}):
        while True:
            try:
                header = self.header()
                param['nonce'] = int(time.time())
                rt = requests.request('POST', self.endpoint + cmd , data = param, headers = header)

                logger.debug('Korbit-Private API[{}, {}]- {} --{}'.format(method, cmd, rt.status_code, rt.text))

                return rt.json()
            except Exception as e: #
                logger.debug('Korbit-Private API Request Error')
                logger.debug(e)

                time.sleep(3)

    def header(self):
        # logger.debug('Korbit Header')

        if not self._token == {}:
            if self.get_token_time <= time.time() - 3500:  # 토큰만료시간이 3600초다. 토큰을받은시간 <= 현재시간-3500인경우, 토큰 만료를 방지하기위해 refresh 한다.
                self.refresh_token(self._token['refresh_token'])
                #self.get_token()

            return {
                'Authorization': "{} {}".format(self._token['token_type'], self._token['access_token'])
            }


    def get_token(self):
        while True:
            try:
                logger.info('Token 획득중.')

                self._user_data = {
                    'client_id': self._client_id,
                    'client_secret': self._client_secret,
                    'username': self._username,
                    'password': self._secret,
                    'grant_type': 'password'
                }
                stat = requests.request('POST', self.endpoint + '/v1/oauth2/access_token', params=self._user_data)

                try:
                    logger.debug('Reason[{}], StatusCode[{}]'.format(stat.reason,stat.status_code))
                except:
                    pass

                self._token = stat.json()
                self.get_token_time = time.time()

                return self._token
            except:
                logger.info('에러로 인한 토큰획득 실패. 30초 뒤 다시 요청합니다.')
                time.sleep(30)

    def refresh_token(self,ref_token):
        self._user_data = {
            'client_id': self._client_id,
            'client_secret': self._client_secret,
            'refresh_token': ref_token,
            'grant_type': 'refresh_token'

        }
        stat = requests.request('POST', self.endpoint + '/v1/oauth2/access_token', params=self._user_data)

        try:
            logger.debug('Reason[{}], StatusCode[{}]'.format(stat.reason, stat.status_code))
        except:
            pass

        self._token = stat.json()
        self.get_token_time = time.time()

        return self._token

    def get_available_coin(self):
        coin = ['BTC_BTC','BTC_ETC', 'BTC_ETH', 'BTC_XRP', 'BTC_BCH']

        return coin

    def get_avg_price(self,coins):
        _amount_price_list = []
        _return_values = []

        for coin in coins:
            total_price = 0
            _bid_count = 0
            total_amount = 0

            my_trade_history = self.public_api('GET','/v1/user/orders',{'currency_pair':coin,'status':'filled'})
            my_trade_history.reverse()

            for i in my_trade_history:
                side = i['side']
                fee = Decimal(i['fee']).quantize(Decimal(10) ** -6)
                price = Decimal(i['filled_total']).quantize(Decimal(10) ** -6)
                amount = Decimal(i['filled_amount']).quantize(Decimal(10) ** -6)

                if side == 'bid':
                    amount -= fee
                else:
                    price -= fee

                if side == 'bid':
                    _amount_price_list.append({ '_price': price ,'_amount': amount})
                    total_price += price
                    total_amount += amount
                    _bid_count += 1
                else:
                    total_amount -= amount

                if total_amount <= 0:
                    _bid_count -=1
                    total_price = 0
                    _amount_price_list.pop(0)

            _values = {coin: { 'avg_price': total_price/_bid_count, 'coin_num': total_amount}}
            _return_values.append(_values)

        return _return_values

    def get_ticker(self):
        ticker_data = {}
        for params in ['btc_krw','etc_krw', 'eth_krw', 'xrp_krw', 'bch_krw']:
            rq = self.public_api('GET','/v1/ticker/detailed',{'currency_pair':params})
            ticker_data[params.split('_')[0].upper()] = rq

        return ticker_data

    def buy(self, coin_name, fiat_amount):
        ### 디버깅용 ###
        # logger.info('[{}]구매, 수량 [{}]'.format(coin_name, fiat_amount))
        #
        # return True,'성공','',1

        ### 디버깅용 ###

        data = {
            'currency_pair': coin_name,
            'type': 'market',
            'fiat_amount': fiat_amount,
        }
        logger.info('[{}]구매, 사용한 KRW [{}]'.format(coin_name, fiat_amount))

        stat = self.private_api('POST', '/v1/user/orders/buy', data)

        check = self.error_check(stat,1)

        return check

    def sell(self, coin_name, coin_amount):
        ### 디버깅용 ###

        # logger.info('[{}]판매, 수량 [{}]'.format(coin_name, coin_amount))
        #
        # return True, '성공', '', 1

        ### 디버깅용 ###

        data = {
            'currency_pair': coin_name,
            'type': 'market',
            'coin_amount': coin_amount,
        }

        logger.info('[{}]판매, 수량 [{}]'.format(coin_name, coin_amount))

        stat = self.private_api('POST', '/v1/user/orders/sell', data)

        check = self.error_check(stat,1)

        return check

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        # alt = Decimal(alt_amount)
        # success, result, error, ts = self.sell('BTC', btc_amount)
        # if not success:
        #     logger.info(error)
        #     time.sleep(ts)
        #     return False
        # while True:
        #     success, result, error, ts = self.buy(currency_pair.split('_')[1], alt_amount)
        #     if success:
        #         break
        #     logger.info(error)
        #     time.sleep(ts)
        # while True:
        #
        #     if td_fee and tx_fee:
        #         break
        # alt *= ((1 - Decimal(td_fee)) ** 2)
        # alt -= Decimal(tx_fee[currency_pair.split('_')[1]])
        # alt = alt.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)
        #
        logger.info('Korbit에서는 BTC만 출금이 가능합니다.')
        return False

    def fee_count(self):
        #Korbit은 2번의 수수료 krw -> btc -> alt // krw -> alt -> btc 가 부과됨.
        return 2

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        while True:
            success, result, error, ts = self.sell(currency_pair.split('_')[1], alt_amount)
            if success:
                break
            logger.info(error)
            time.sleep(ts)
        while True:
            success, result, error, ts = self.buy('BTC', btc_amount)
            if success:
                break
            logger.info(error)
            time.sleep(ts)

    def withdraw(self,coin, amount, to_address, payment_id=None):
        '''
        현재 korbit은 출금이 비트코인밖에 되지않기때문에 따로 payment_id를 체크하는
        함수가없다.

        '''

        ### 디버깅용 ###
        # logger.info('withdraw - [{}][{}][{}][{}] 받았음.'.format(coin,amount,to_address,payment_id))
        #
        # return True,'suc','',0
        ### 디버깅용 ###

        params = {
            'currency' : coin,
            'amount' : amount,
            'address': to_address,
            'fee_priority':'normal',
        }
        stat = self.private_api('POST','/v1/user/coins/out',params)

        check = self.error_check(stat,1)

        return check

    async def get_trading_fee(self):# async
        coin_fee = 0.002 # 현재 모든코인은 0.002의 trading 수수료를 가지고있음.

        # av_coin = self.get_available_coin()
        # coin_fee = {}
        # for coin_name in av_coin:
        #     krw_st = coin_name.split('_')[1].lower()+"_krw"
        #     while True:
        #         _trade_fee_info = self.public_api('GET','/v1/user/volume',{'currency_pair': krw_st})
        #
        #         check = self.error_check(_trade_fee_info, 1)
        #
        #         if check[0]: # check한게 True인경우
        #             break
        #         time.sleep(check[3])
        #
        #     coin_fee[coin_name.split('_')[1]] = float(_trade_fee_info[krw_st]['taker_fee'])
        #
        return True,coin_fee,'',0

    async def get_transaction_fee(self):# async

        transaction_fee = {
            'BTC': 0.001,
            # 'BCH': 0.0005,
            # 'ETH': 0.01,
            # 'ETC': 0.01,
            # 'XRP': 0.2,
            # 'LTC': 0.01,
            # 'ZIL': 30,
        }
        return True,transaction_fee,'',0

    async def get_deposit_addrs(self): # async
        stat = self.public_api('GET','/v1/user/accounts')

        check = self.error_check(stat,60
                                 )
        modi_deposit = {}

        for k,i in check[1]['deposit'].items():
            modi_deposit[k.upper()] = i['address']

            if k == 'xrp':
                modi_deposit['XRPTAG'] = i['destination_tag']
        check[1] = modi_deposit

        return check

    async def balance(self):# async
        stat = self.public_api('GET','/v1/user/balances')

        check = self.error_check(stat,60
                                 )
        if check[0]:
            modi_check = {}
            for coin in check[1].keys():
                modi_check[coin] = check[1][coin]['available']
            check[1] = modi_check
        return check

    async def get_curr_avg_orderbook(self, coin_name,btc_sum = 1):
        btc_avg_list = []
        avg_order_book = {}
        try:
            for _currency_pair in ['BTC_BTC']+coin_name:
                average_list = []
                avg_order_book[_currency_pair] = {}

                for order_type in ['asks', 'bids']:
                    _order_amount = 0
                    _order_sum = 0

                    while True:
                        _list = self.public_api('GET','/v1/orderbook',{'currency_pair': _currency_pair.split('_')[1].lower()+'_krw'})[order_type]
                        _stat = self.error_check(_list,10)

                        if _stat[0]:
                            break
                        time.sleep(_stat[3])

                    _list.reverse()

                    for _info in _list:
                        _order_amount += Decimal(_info[1])
                        _order_sum += (Decimal(_info[0]) * Decimal(_info[1])).quantize(Decimal(10) ** -8)

                        if _order_amount >= btc_sum:

                            if _currency_pair == 'BTC_BTC':
                                btc_avg_list.append((_order_sum / _order_amount).quantize(Decimal(10) ** -8))
                            else:
                                average_list.append((_order_sum / _order_amount).quantize(Decimal(10) ** -8))

                            break

                if _currency_pair == 'BTC_BTC':
                    bids_return_value = btc_avg_list[1]
                    asks_return_value = btc_avg_list[0]

                else:
                    bids_return_value = Decimal(average_list[1]/btc_avg_list[0]).quantize(Decimal(10) ** -8) #[0]-->ask [1]-->bids
                    asks_return_value = Decimal(average_list[0]/btc_avg_list[1]).quantize(Decimal(10) ** -8)

                avg_order_book[_currency_pair] = {'asks': asks_return_value,'bids': bids_return_value}

            del avg_order_book['BTC_BTC']

            return True, avg_order_book, '', 0
        except:
            return False, '','get_curr_orderbook_fail',1
    #secondary, default_btc, bal_n_crncy[2])

    async def compare_orderbook(self, other, coins=[], default_btc=1):
        # currency_pairs = ['BTC_'+ coin for coin in coins if coin !="BTC"]
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            # korbit_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs, default_btc),
            #                                                     other.get_curr_avg_orderbook(currency_pairs, default_btc))

            korbit_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(coins, default_btc),
                                                                other.get_curr_avg_orderbook(coins, default_btc))

            success, korbit_avg_orderbook, err, st = korbit_result
            success2, other_avg_orderbook, err2, st2 = other_result

            if 'BTC' in coins:
                coins.remove('BTC')

            if success and success2:
                m_to_s = {}
                for currency_pair in coins:
                    m_ask = korbit_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in coins:
                    m_bid = korbit_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                ret = (korbit_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m})

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

    # async def korbit__korbit(self, korbit, default_btc):
    #     korbit_currency_pair = korbit.get_available_coin()
    #     korbit_currency_pair = self.get_available_coin()
    #     loop = asyncio.get_event_loop()
    #
    #     fut = loop.run_in_executor(None, self.get_curr_avg_orderbook, korbit_currency_pair, default_btc)
    #     korbit_avg_orderbook = await fut
    #
    #     fut = loop.run_in_executor(None, korbit.get_curr_avg_orderbook,korbit_currency_pair,default_btc)
    #     korbit_avg_orderbook = await fut
    #
    #     k_to_b = {}
    #     for currency_pair in korbit_currency_pair:
    #         try:
    #             k_ask = korbit_avg_orderbook[currency_pair]['asks']
    #             b_bid = korbit_avg_orderbook[currency_pair]['bids']
    #             k_to_b[currency_pair] = float(((b_bid - k_ask) / k_ask).quantize(Decimal(10)**-8))
    #         except:
    #             pass
    #
    #     b_to_k = {}
    #     for currency_pair in korbit_currency_pair:
    #         try:
    #             k_bid = korbit_avg_orderbook[currency_pair]['bids']
    #             b_ask = korbit_avg_orderbook[currency_pair]['asks']
    #             b_to_k[currency_pair] = float(((k_bid - b_ask) / b_ask).quantize(Decimal(10)**-8))
    #         except:
    #             pass
    #
    #     return {'k_to_b': k_to_b, 'b_to_k': b_to_k}

if __name__ == '__main__':
    api_key = 'VbKNWsKsRm8BgJHftXcYIPlfvm0AQULkdiIv17zbUYq7vBqn029ZxUe0rMQbu'
    secret = 'zhRWiKM7feoTDIK5OUnTZ5tZuWgJklhYlfdxan80MjiXATvW4pNk8kLnwqvnu'
    email = 'goodmoskito@gmail.com'
    password = '!moskito235'

    a = Korbit(api_key,secret,email,password)
    loop = asyncio.get_event_loop()
    while True:
        b = loop.run_until_complete(a.balance())
        print(b)