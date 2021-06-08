import hmac
import hashlib
import requests
import logging
from urllib.parse import urlencode
from decimal import *
import asyncio
import time
from zlib import compress
from base64 import b64encode

binance_logger = logging.getLogger(__name__)
binance_logger.setLevel(logging.DEBUG)

fmt = logging.Formatter('[%(asctime)s - %(lineno)d] %(message)s')
f_hdlr = logging.FileHandler('binance.log')
f_hdlr.setLevel(logging.DEBUG)
f_hdlr.setFormatter(fmt)

s_hdlr = logging.StreamHandler()
s_hdlr.setLevel(logging.INFO)
s_hdlr.setFormatter(fmt)

binance_logger.addHandler(f_hdlr)
binance_logger.addHandler(s_hdlr)


class Binance:
    def __init__(self, key, secret):
        self._endpoint = 'https://api.binance.com'
        self._key = key
        self._secret = secret
        self.exchange_info = self.get_exchange_info()

        # self._request_limit = 1200 # 분당 request 가능횟수
        # self._orders_limit = 10 #초당 order 가능 횟수

    def servertime(self):
        stat = self.public_api('/api/v1/time')

        return stat['serverTime']

    def private_api(self, method, path, params={}):
        query = urlencode(sorted(params.items()))

        # if self._nonce == 0:
        while True:
            try:
                _nonce = self.servertime()

                query += "&timestamp={}".format(_nonce)
                # query += "&recvWindows=10000"
                sign = hmac.new(self._secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()

                query += "&signature={}".format(sign)
                req = requests.request(method, self._endpoint + path, params=query, headers={"X-MBX-APIKEY": self._key})
                data = req.json()
                binance_logger.debug(
                    'Binance-Private API[{}, {}]- {} -{}'.format(path, params, req.status_code,
                                                                 b64encode(compress(req.content, 9))))
                break
            except:
                time.sleep(3)

        try:
            if not data['success'] == False:
                raise 0
            else:
                try:
                    binance_logger.debug('Binance-Private API 에러, 메세지 = [{}]'.format(data['msg']))
                except:  # 만약 입금주소가 점검중인경우, {'success':False}만 남기때문에 False를 반환해서 그냥 넘기게한다.
                    binance_logger.debug('Binance-Private API 입금주소 점검으로 인한 에러')

                    return False
        except:
            return data

    def public_api(self, path, params={}):

        while True:
            while True:
                try:
                    req = requests.get(self._endpoint + path, params=params)
                    _data = req.json()
                    break
                except:
                    time.sleep(5)

            binance_logger.debug('Binance-Public API[{}, {}]- {} -{}'.format(path, params, req.status_code,
                                                                             b64encode(compress(req.content, 9))))
            try:
                if _data['success'] == False:
                    pass
                else:
                    raise 0
            except:
                return _data

            time.sleep(5)

    def get_exchange_info(self):  # API에서 제공하는 서비스 리턴
        stat = self.public_api('/api/v1/exchangeInfo')
        # _av_coin = []
        _step_size = {}
        for i in stat['symbols']:
            flag_symbol = i['symbol'][-3:]  # BTC ETH와 같은 기축통화
            if 'BTC' in flag_symbol:  # 기준이 BTC인경우
                coin_name = flag_symbol + '_' + i['symbol'][:-3]  # BNBBTC --> BTC_BNB 이런식으로 변경
                # _av_coin.append(coin_name)
                _step_size.update({coin_name: i['filters'][1]['stepSize']})

        return _step_size  # {'av_coin':_av_coin,'step_info':_step_size}

    def get_step_size(self, symbol):
        if symbol == 'BTC_BCH':
            symbol = 'BTC_BCC'
        step_size = self.exchange_info[symbol]

        return Decimal('{0:g}'.format(float(step_size)))

    def get_available_coin(self):  # API에서 제공하는 서비스 리턴
        coin = self.exchange_info.keys()
        _list = []
        for _av in coin:
            _list.append(_av)
        return _list

    def get_avg_price(self, coins):  # 내거래 평균매수가
        _amount_price_list = []
        _return_values = []

        for coin in coins:
            total_price = 0
            _bid_count = 0
            total_amount = 0

            history = self.public_api('/api/v3/allOrders', {'symbol': coin})
            history.reverse()
            for _data in history:
                side = _data['side']
                # fee = Decimal(0.1) # 0.1%의 거래 수수료 부과
                n_price = float(_data['price'])
                price = Decimal(n_price - (n_price * 0.1)).quantize(Decimal(10) ** -6)
                amount = Decimal(_data['origQty']).quantize(Decimal(10) ** -6)
                if side == 'BUY':
                    _amount_price_list.append({
                        '_price': price,
                        '_amount': amount
                    })
                    total_price += price
                    total_amount += amount
                    _bid_count += 1
                else:  # SELL == 매도
                    total_amount -= amount  # 300 = -300 + 500 = -200
                if total_amount <= 0:
                    _bid_count -= 1
                    total_price = 0
                    _amount_price_list.pop(0)  #

            _values = {coin: {
                'avg_price': total_price / _bid_count,
                'coin_num': total_amount
            }}
            _return_values.append(_values)

        return _return_values

    def get_curr_avg_orderbook(self, coin_name, btc_sum=1):  # 상위 평균매도/매수가 구함
        avg_order_book = {}

        for _currency_pair in coin_name:
            if _currency_pair == 'BTC_BTC':
                continue
            convt_name = _currency_pair.split('_')
            if convt_name[1] == 'BCH':  # 비트코인캐시코빗은 BCH 바이낸스는 BCC다.
                convt_name[1] = 'BCC'
            avg_order_book[_currency_pair] = {}
            _book = self.public_api('/api/v1/depth', {'symbol': convt_name[1] + convt_name[0]})
            for _type in ['asks', 'bids']:
                _order_amount = 0
                _order_sum = 0
                _info = _book[_type]
                for _data in _info:
                    _order_amount += Decimal(_data[1])  # 0 - price 1 - qty
                    _order_sum += (Decimal(_data[0]) * Decimal(_data[1])).quantize(Decimal(10) ** -8)
                    if _order_amount >= Decimal(btc_sum):
                        _v = ((_order_sum / _order_amount).quantize(Decimal(10) ** -8))
                        avg_order_book[_currency_pair][_type] = _v
                        break

        return avg_order_book

    def balance(self):  # 일단은 밸런스, 테스트해보고 0인 값도 나온다면 available coin도 커버가능
        balance = {}
        while True:
            rq = self.private_api('GET', '/api/v3/account')
            try:
                if rq['code']:  # 에러시 나오는 key
                    time.sleep(10)
                    continue
            except:
                pass
            for _info in rq['balances']:
                if _info['asset'] == 'BCC':
                    _info['asset'] = 'BCH'
                if float(_info['free']) > 0:
                    balance[_info['asset']] = float(_info['free'])  # asset-> 코인이름 free -> 거래가능한 코인수
            break
        return balance

    def get_available_coin(self):  # API에서 제공하는 서비스 리턴
        stat = self.public_api('/api/v1/exchangeInfo')
        _av_coin = []

        for i in stat['symbols']:
            flag_symbol = i['symbol'][-3:]  # BTC ETH와 같은 기축통화
            if 'BTC' in flag_symbol:  # 기준이 BTC인경우
                coin_name = flag_symbol + '_' + i['symbol'][:-3]  # BNBBTC --> BTC_BNB 이런식으로 변경 // strtBTC ?
                _av_coin.append(coin_name)

        return _av_coin

    # def get_check_orders(self, currency_pair='BTC_ETH'):  # 내가 거래했던 주문들을 조회함. offset=0 limit=40
    #     order_stat = self.private_api('/v1/user/orders',{'currency_pair': currency_pair, 'status':'filled'})#filled-->체결된
    #     return order_stat.json()


    def trade(self, coin, amount, side):
        params = {
            'symbol': coin,
            'side': side,  # buy,sell
            'quantity': amount,
            'type': 'MARKET'
        }
        return self.private_api('POST', '/api/v3/order', params)

    # /api/v1/depth-->orderbook

    def withdrawal_coin(self, coin, address, amount, tag=None):
        # coin_sp = coin.split('_')[1]
        if coin == 'BCH':
            coin = 'BCC'
        params = {
            'asset': coin,
            'address': address,
            'amount': amount}

        if tag:
            tag_dic = {'addressTag': tag}
            params.update(tag_dic)

        rq = self.private_api('POST', '/wapi/v3/withdraw.html', params)

        return rq

    async def get_deposit_addrs(self):
        rq_dic = {}
        coin_lists = self.get_available_coin()
        coin_lists.append('BTC_BTC')
        for coin in coin_lists:
            coin_sp = coin.split('_')[1]
            if coin_sp == 'BCH':
                coin_sp = 'BCC'
            params = {'asset': coin_sp}
            rq = self.private_api('GET', '/wapi/v3/depositAddress.html', params)
            if not rq:
                continue

            rq_dic[coin_sp] = rq['address']

            try:
                tag = rq['addressTag']
            except:
                tag = ''

            if not tag == '':
                rq_dic[coin_sp + 'TAG'] = tag

        return True, rq_dic, '', 0

    async def binance__korbit(self, korbit, default_btc):
        korbit_currency_pair = korbit.get_available_coin()
        binance_currency_pair = self.get_available_coin()
        loop = asyncio.get_event_loop()

        fut = loop.run_in_executor(None, self.get_curr_avg_orderbook, binance_currency_pair,
                                   default_btc)  # 코빗에서 지원하는 코인을 불러와서 바이낸스의 가격을 가져온다.
        binance_avg_orderbook = await fut

        fut = loop.run_in_executor(None, korbit.get_curr_avg_orderbook, korbit_currency_pair, default_btc)
        korbit_avg_orderbook = await fut

        b_to_k = {}
        for currency_pair in korbit_currency_pair:
            try:
                b_ask = korbit_avg_orderbook[currency_pair]['asks']
                k_bid = binance_avg_orderbook[currency_pair]['bids']
                b_to_k[currency_pair] = float(((k_bid - b_ask) / b_ask).quantize(Decimal(10) ** -8))
            except:
                # 2개 거래소중에 중복되는 코인이 없는경우.
                pass

        k_to_b = {}
        for currency_pair in korbit_currency_pair:
            try:
                b_bid = korbit_avg_orderbook[currency_pair]['bids']
                k_ask = binance_avg_orderbook[currency_pair]['asks']
                k_to_b[currency_pair] = float(((b_bid - k_ask) / k_ask).quantize(Decimal(10) ** -8))  # 일반마진
            except:
                # 2개 거래소중에 중복되는 코인이 없는경우.
                pass

        return {'k_to_b': k_to_b, 'b_to_k': b_to_k}

    async def binance__coinone(self, coinone, default_btc):

        coinone_currency_pair = list(coinone.transaction_fee().keys())
        binance_currency_pair = self.get_available_coin()
        loop = asyncio.get_event_loop()

        fut = loop.run_in_executor(None, self.get_curr_avg_orderbook, binance_currency_pair, default_btc)
        binance_avg_orderbook = await fut

        fut = loop.run_in_executor(None, coinone.get_curr_avg_orderbook, coinone_currency_pair, default_btc)
        coinone_avg_orderbook = await fut

        b_to_c = {}
        for currency_pair in binance_currency_pair:
            try:
                b_ask = binance_avg_orderbook[currency_pair]['asks']
                c_bid = coinone_avg_orderbook[currency_pair]['bids']
                b_to_c[currency_pair] = float(((c_bid - b_ask) / b_ask).quantize(Decimal(10) ** -8))
            except:
                pass

        c_to_b = {}
        for currency_pair in coinone_currency_pair:
            try:
                b_bid = binance_avg_orderbook[currency_pair]['bids']  # 코빗평균매도가
                c_ask = coinone_avg_orderbook[currency_pair]['asks']  # 바이낸스평균매수가

                b_to_c[currency_pair] = float(((b_bid - c_ask) / c_ask).quantize(Decimal(10) ** -8))  # 일반마진
            except:
                pass

        return {'b_to_c': b_to_c, 'c_to_b': c_to_b}

    async def binance__bithumb(self, bithumb, default_btc, currency_pairs):
        # binance_currency_pair = self.get_available_coin()
        # bithumb_currency_pair = bithumb.get_available_coin()
        loop = asyncio.get_event_loop()

        fut = [
            loop.run_in_executor(None, self.get_curr_avg_orderbook, currency_pairs, default_btc),
            loop.run_in_executor(None, bithumb.get_curr_avg_orderbook, default_btc)
        ]

        binance_avg_orderbook, bithumb_avg_orderbook = await asyncio.gather(*fut)

        m_to_s = {}
        for currency_pair in currency_pairs:
            m_ask = binance_avg_orderbook[currency_pair]['asks']
            s_bid = bithumb_avg_orderbook[currency_pair]['bids']
            m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

        s_to_m = {}
        for currency_pair in currency_pairs:
            m_bid = binance_avg_orderbook[currency_pair]['bids']
            s_ask = bithumb_avg_orderbook[currency_pair]['asks']
            s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))  # 일반마진

        return {'m_to_s': m_to_s, 's_to_m': s_to_m, 'm_o_b': binance_avg_orderbook, 's_o_b': bithumb_avg_orderbook}

    # async def coinone__bithumb(self, bithumb, default_btc):
    #     coinone_currency_pair = list(self.transaction_fee().keys())
    #     bithumb_currency_pair = list(bithumb.get_available_coin())
    #
    #     loop = asyncio.get_event_loop()
    #     fut = loop.run_in_executor(None, self.get_curr_avg_orderbook, coinone_currency_pair, default_btc)
    #     coinone_avg_orderbook = await fut
    #
    #     fut = loop.run_in_executor(None, bithumb.get_curr_avg_orderbook, default_btc)
    #     bithumb_avg_orderbook = await fut
    #
    #     c_to_b = {}
    #     for currency_pair in bithumb_currency_pair:
    #         try:
    #             c_ask = coinone_avg_orderbook[currency_pair]['asks']
    #             b_bid = bithumb_avg_orderbook[currency_pair]['bids']
    #             c_to_b[currency_pair] = float(((b_bid - c_ask) / c_ask).quantize(Decimal(10) ** -8))
    #         except KeyError:
    #             #   두 거래소 중 한쪽에만 있는 currency 일 경우 제외한다.
    #             continue
    #
    #     b_to_c = {}
    #     for currency_pair in bithumb_currency_pair:
    #         try:
    #             c_bid = coinone_avg_orderbook[currency_pair]['bids']
    #             b_ask = bithumb_avg_orderbook[currency_pair]['asks']
    #             b_to_c[currency_pair] = float(((c_bid - b_ask) / c_bid).quantize(Decimal(10) ** -8))
    #         except KeyError:
    #             #   위와 동일
    #             continue
    #
    #     for key in coinone_avg_orderbook.keys():
    #         for key2 in ['bids', 'asks']:
    #             coinone_avg_orderbook[key][key2] = float(coinone_avg_orderbook[key][key2].quantize(Decimal(10) ** -8))
    #             #   json 으로 전송하기 위해 Decimal을 float으로 바꿔줌
    #     for key in bithumb_avg_orderbook.keys():
    #         for key2 in ['bids', 'asks']:
    #             bithumb_avg_orderbook[key][key2] = float(bithumb_avg_orderbook[key][key2].quantize(Decimal(10) ** -8))
    #
    #     return {'c_to_b': c_to_b, 'b_to_c': b_to_c, 'c_o_b': coinone_avg_orderbook, 'b_o_b': bithumb_avg_orderbook}

    async def get_transaction_fee(self):
        _fee_info = {}
        try:
            ret = requests.get('https://www.binance.com/assetWithdraw/getAllAsset.html', timeout=60)
            _data_list = ret.json()
            for f in _data_list:
                if f['assetCode'] == 'BCC':
                    f['assetCode'] = 'BCH'
                _fee_info[f['assetCode']] = f['transactionFee']
        except:
            binance_logger.exception('binance requests failed')
            return False, '', 'binance requests failed', 3

        return True, _fee_info, '', 0

    def get_ticker(self):
        rq = self.public_api('/api/v1/ticker/24hr')

        return rq

    async def get_trading_fee(self):

        return True, 0.001, '', 0

    def fee_count(self):
        return 1