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
import base64
import time
import configparser
import aiohttp

huobi_logger = logging.getLogger(__name__)
huobi_logger.setLevel(logging.DEBUG)

f_hdlr = logging.FileHandler('huobi_logger.log')
s_hdlr = logging.StreamHandler()

huobi_logger.addHandler(f_hdlr)
huobi_logger.addHandler(s_hdlr)
cfg = configparser.ConfigParser()
cfg.read('Settings.ini')


class Huobi:
    def __init__(self, key, secret):
        self._endpoint = 'https://api.huobi.pro'
        self.market_endpoint = 'https://api.huobi.pro/market'

        self._key = key
        self._secret = secret
        self.signature_version = 2

        self.transaction_list = [
            'USDT', 'BTC', 'ETH', 'HT', 'BCH', 'XRP',
            'LTC', 'ADA', 'EOS', 'XEM', 'DASH', 'TRX',
            'LSK', 'ICX', 'QTUM', 'ETC', 'OMG', 'HSR',
            'ZEC', 'BTS', 'SNT', 'SALT', 'GNT', 'CMT',
            'BTM', 'PAY', 'KNC', 'POWR', 'BAT', 'DGD',
            'VEN', 'QASH', 'ZRX', 'GAS', 'MANA', 'ENG',
            'CVC', 'MCO', 'MTL', 'RDN', 'STORJ', 'SRN',
            'CHAT', 'LINK', 'ACT', 'TNB', 'QSP', 'REQ',
            'RPX', 'APPC', 'RCN', 'ADX', 'TNT', 'OST',
            'ITC', 'LUN', 'GNX', 'AST', 'EVX', 'MDS',
            'SNC', 'PROPY', 'EKO', 'NAS', 'WAX', 'WICC',
            'TOPC', 'SWFTC', 'DBC', 'ELF', 'AIDOC', 'QUN',
            'IOST', 'YEE', 'DAT', 'THETA','LET', 'DTA', 'UTK',
            'MEET', 'ZIL', 'SOC', 'RUFF', 'OCN', 'ELA', 'ZLA',
            'STK', 'WPR','MTN', 'MTX', 'EDU', 'BLZ', 'ABT', 'ONT', 'CTXC'
        ]

        self.get_headers = {
            "Content-type": "application/x-www-form-urlencoded",
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36'
        }

        self.post_headers = {
            "Accept": "application/json",
            'Content-Type': 'application/json'
        }

    def get_account_id(self):
        for _ in range(10):
            id_suc, id_data, id_msg, id_time = self.api_request('GET', '/v1/account/accounts')

            if id_suc:
                self.account_id = id_data['data'][0]['id']

                return True, self.account_id, '', 0

            else:
                huobi_logger.debug(id_msg)
                time.sleep(id_time)

        else:
            return False, '', '[Huobi]AccountID를 가져오는데 실패했습니다. [{}]'.format(id_msg), id_time

    # def servertime(self):
    #     suc, stat, msg, times = self.http_request('GET', self._endpoint + '/v1/common/timestamp')
    #
    #     if not suc:
    #         return False, stat, msg, times
    #
    #     return stat['data']

    def encrypto(self, method, path, params, sign_data):
        if method == 'GET':
            params.update(sign_data)
            encode_qry = urlencode(sorted(params.items()))

        else:
            encode_qry = urlencode(sorted(sign_data.items()))

        payload = [method, 'api.huobi.pro', path, encode_qry]
        payload = '\n'.join(payload)

        sign = hmac.new(self._secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()

        return base64.b64encode(sign).decode()

    def api_request(self, method, path, params=None):
        if params is None:
            params = {}

        sign_data = {
                    'AccessKeyId': self._key,
                    'SignatureMethod': 'HmacSHA256',
                    'SignatureVersion': self.signature_version,
                    'Timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
                     }

        sign = self.encrypto(method, path, params, sign_data)
        url = self._endpoint + path

        if method == 'GET':
            params['Signature'] = sign

        else:
            sign_data['Signature'] = sign
            url += '?' + urlencode(sign_data)

        hrq_suc, hrq_data, hrq_msg, hrq_time = self.http_request(method, url, params)

        return hrq_suc, hrq_data, hrq_msg, hrq_time

    def http_request(self, method, path, params=None):
        if params is None:
            params = {}

        try:
            if method == 'GET':
                postdata = urlencode(params)
                rq = requests.request(method, path, params=postdata, headers=self.get_headers)

            else:
                postdata = json.dumps(params)
                rq = requests.request(method, path, data=postdata, headers=self.post_headers)

            rqj = rq.json()

            if rqj['status'] in 'error':
                return False, '', rqj['err-msg'], 1
            else:
                return True, rqj, '', 0
        except Exception as ex:
            return False, '', '서버와 통신에 실패하였습니다 = [{}]'.format(ex), 1

    def get_precision(self, pair):
        return True, (-8, -8), '', 0

    def buy(self, coin, amount):
        huobi_logger.info('구매, Coin-[{}] Amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = coin.split('_')
        currency_pair = coin[1].lower() + coin[0].lower()

        params = {
                    'account-id': self.account_id,
                    'symbol': currency_pair,
                    'amount': '{}'.format(amount).strip(),
                    'type': 'buy-market'
                  }

        suc, data, msg, times = self.api_request('POST', '/v1/order/orders/place', params)

        return suc, data, msg, times

    def sell(self, coin, amount):
        huobi_logger.info('판매, Coin-[{}] Amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = coin.split('_')
        currency_pair = coin[1].lower() + coin[0].lower()

        params = {
                    'account-id': str(self.account_id),
                    'symbol': currency_pair,
                    'amount': '{}'.format(amount).strip(),
                    'type': 'sell-market'
                  }
        suc, data, msg, times = self.api_request('POST', '/v1/order/orders/place', params)

        return suc, data, msg, times

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        suc, data, msg, times = self.buy(currency_pair, btc_amount)

        if suc:
            coin = currency_pair.split('_')[1]  # 보내야하는 alt의 양 계산함.

            precision = alt_amount.as_tuple().exponent
            alt_amount *= (1 - Decimal(td_fee))
            alt_amount -= Decimal(tx_fee[coin])
            alt_amount = alt_amount.quantize(Decimal(10)**precision, rounding=ROUND_DOWN)

            return suc, alt_amount, msg, times

        else:
            huobi_logger.info(msg)

            return suc, data, '[Huobi]BaseToAlt 거래에 실패했습니다[{}]'.format(msg), times

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        coin = currency_pair[1]

        for _ in range(10):
            suc, data, msg, times = self.sell(coin, alt_amount)

            if suc:
                huobi_logger.debug('AltToBase 거래에 성공했습니다.')

                return suc, data, msg, times

            else:
                huobi_logger.info(msg)
                time.sleep(times)

        else:
            return suc, data, '[Huobi]AltToBase 거래에 실패했습니다[{}]'.format(msg), times

    def fee_count(self):
        return 1

    def withdraw(self, coin, amount, to_address, payment_id=None):
        huobi_logger.info('출금, Coin-[{}] Amount-[{}] ToAddress-[{}] PaymentId-[{}] 입력되었습니다.'.format(coin, amount, to_address, payment_id))

        params = {
                    'currency': coin.lower(),
                    'address': to_address,
                    'amount': '{}'.format(amount)
        }
        if payment_id:
            tag_dic = {'addr-tag': payment_id}
            params.update(tag_dic)

        suc, data, msg, times = self.api_request('POST', '/v1/dw/withdraw/api/create', params)

        if not suc:
            huobi_logger.debug('출금 값을 가져오지 못했습니다. [{}]'.format(msg))

            return False, '', '[Huobi]출금 값을 가져오지 못했습니다. [{}]'.format(msg), 1

        else:
            return suc, data, msg, times

    def get_available_coin(self):
        suc, data, msg, times = self.http_request('GET', self._endpoint + '/v1/common/currencys')

        if not suc:
            huobi_logger.debug('사용가능한 코인 값을 가져오지 못했습니다. [{}]'.format(msg))

            return False, '', '[Huobi]사용가능한 코인 값을 가져오지 못했습니다. [{}]'.format(msg), 1

        else:
            return suc, data, msg, times

    def get_candle(self, coin, unit, count):
        path = '/'.join([self.market_endpoint, 'history', 'kline'])

        params = {
            'symbol': coin,
            #  period = 1min, 5min, 15min, 30min, 60min, 1day, 1mon, 1week, 1year
            'period': '{}min'.format(unit),
            'size': count
        }

        suc, data, msg, time_ = self.http_request('get', path, params)

        if not suc:
            return suc, data, msg

        history = {
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': [],
            'timestamp': [],
        }

        try:
            for info in data['data']:  # 리스트가 늘어날 수도?
                history['open'].append(info['open'])
                history['high'].append(info['high'])
                history['low'].append(info['low'])
                history['close'].append(info['close'])
                history['volume'].append(info['vol'])
                history['timestamp'].append(data['ts'])

            for key in history.keys():
                #  거래소마다 다를 수 있음
                history[key].reverse()

            return True, history, ''

        except Exception as ex:
            return False, '', 'history를 가져오는 과정에서 에러가 발생했습니다. =[{}]'.format(ex)

    async def async_api_request(self, s, method, path, params=None):
        sign_data = {
                    'AccessKeyId': self._key,
                    'SignatureMethod': 'HmacSHA256',
                    'SignatureVersion': self.signature_version,
                    'Timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
                     }

        sign = self.encrypto(method, path, params, sign_data)
        url = self._endpoint + path

        if method == 'GET':
            params['Signature'] = sign
        else:
            sign_data['Signature'] = sign
            url += '?' + urlencode(sign_data)

        suc, data, msg, times = await self.async_http_request(s, method, url, params)

        return suc, data, msg, times

    async def async_http_request(self, s, method, path, params=None):
        if params is None:
            params = {}

        if method == 'GET':
            postdata = urlencode(params)
            rq = await s.get(path, params=postdata)
        else:
            postdata = json.dumps(params)
            rq = await s.post(path, data=postdata)

        try:
            rq = await rq.text()
            rqj = json.loads(rq)

            if rqj['status'] in 'error':
                return False, '', rqj['status'], 1
            else:
                return True, rqj, '', 0

        except Exception as ex:
            return False, '', '서버와 통신에 실패하였습니다 = [{}]'.format(ex), 1

    async def get_avg_price(self, coins):  # 내거래 평균매수가
        _amount_price_list = []
        _return_values = []

        async with aiohttp.ClientSession(headers=self.get_headers) as sync:
            try:
                for coin in coins:
                    currency_pair = coin.split('_')
                    currency_pair = currency_pair[1].lower() + currency_pair[0].lower()

                    total_price, bid_count, total_amount = 0, 0, 0

                    suc, history, msg, times = await self.async_http_request(sync, 'GET',
                                                                             self._endpoint + '/market/history/trade',
                                                                             {'symbol': currency_pair})
                    if suc:
                        history_data = history['data']
                        history_data.reverse()
                        for _data in history_data:
                            spc_data = _data['data']

                            side = spc_data['direction']
                            n_price = float(_data['price'])
                            price = Decimal(n_price - (n_price * 0.1)).quantize(Decimal(10) ** -6)
                            amount = Decimal(_data['amount']).quantize(Decimal(10) ** -6)
                            if side == 'buy':
                                _amount_price_list.append({
                                    '_price': price,
                                    '_amount': amount
                                })
                                total_price += price
                                total_amount += amount
                                bid_count += 1
                            else:
                                total_amount -= amount
                            if total_amount <= 0:
                                bid_count -= 1
                                total_price = 0
                                _amount_price_list.pop(0)

                        _values = {coin: {
                            'avg_price': total_price / bid_count,
                            'coin_num': total_amount
                        }}
                        _return_values.append(_values)

                    else:
                        return False, '', '[Huobi] 코인 평균매수가 값을 가져오는데 실패했습니다. [{}]'.format(msg), 1

                return True, _return_values, '', 1

            except Exception as ex:
                return False, '', '[Huobi]코인 평균매수가 값을 가져오는데 실패했습니다. [{}]'.format(ex), 1

    async def get_transaction_fee(self):
        _fee_info = {
            'XEM': 4.0, 'EOS': 0.5, 'POWR': 2.0, 'EDU': 500.0,
            'BTS': 5.0, 'LUN': 0.05, 'HT': 1.0, 'REQ': 5.0,
            'WICC': 2.0, 'MDS': 20.0, 'LINK': 1.0, 'MTN': 5.0,
            'LSK': 0.1, 'CVC': 2.0, 'BTC': 0.001, 'SRN': 0.5,
            'MTL': 0.2, 'BAT': 5.0, 'OST': 1.0, 'RDN': 1.0,
            'ETH': 0.01, 'NAS': 0.2, 'QASH': 1.0, 'AIDOC': 10.0,
            'CHAT': 2.0, 'OMG': 0.1, 'UTK': 2.0, 'GNX': 5.0,
            'TRX': 20.0, 'ACT': 0.01, 'ZLA': 1.0, 'ADX': 0.5,
            'ADA': 10.0, 'PAY': 0.5, 'XRP': 0.1, 'GNT': 5.0,
            'KNC': 1.0, 'WAX': 1.0, 'DAT': 10.0, 'CMT': 20.0,
            'USDT': 10.0, 'SWFTC': 100.0, 'BCH': 0.0, 'RCN': 10.0,
            'TOPC': 20.0, 'QSP': 10.0, 'BTM': 2.0, 'QUN': 30.0,
            'SNT': 50.0, 'QTUM': 0.01, 'EKO': 20.0, 'PROPY': 0.5,
            'ITC': 2.0, 'OCN': 100.0, 'SNC': 5.0, 'THETA': 10.0,
            'ELF': 5.0, 'STK': 10.0, 'HSR': 0.0001, 'DBC': 10.0,
            'RPX': 2.0, 'LTC': 0.001, 'ZIL': 100.0, 'LET': 30.0,
            'ELA': 0.005, 'MANA': 10.0, 'EVX': 0.5, 'ETC': 0.01,
            'AST': 5.0, 'MEET': 10.0, 'STORJ': 2.0, 'ENG': 0.5,
            'TNB': 50.0, 'SOC': 10.0, 'MTX': 2.0, 'RUFF': 20.0,
            'GAS': 0.0, 'YEE': 50.0, 'ICX': 0.2, 'ONT': 0.02,
            'ZEC': 0.001, 'IOST': 100.0, 'APPC': 0.5, 'ZRX': 5.0,
            'ABT': 2.0, 'WPR': 10.0, 'TNT': 20.0, 'VEN': 2.0,
            'DGD': 0.01, 'MCO': 0.2, 'DASH': 0.002, 'BLZ': 2.0,
            'DTA': 100.0, 'SALT': 0.1, 'CTXC': 2.0, 'IOTA': 0.0,
            'BTG': 0.01
        }

        _fee_info = {key: Decimal(_fee_info[key]).quantize(Decimal(10)**-8) for key in _fee_info.keys()}

        return True, _fee_info, '', 0

    async def get_trading_fee(self):
        return True, 0.002, '', 0

    async def get_deposit_addrs(self):
        gac_suc, gac_data, gac_msg, gac_times = self.get_available_coin()

        if gac_suc:
            try:
                coins = gac_data['data']
                coin_addrs = {}
                async with aiohttp.ClientSession(headers=self.get_headers) as s:

                    for coin in coins:
                        suc, data, msg, times = await self.async_api_request(s, "GET", '/v1/query/deposit-withdraw',
                                                                             {"currency": coin, "type": "deposit",
                                                                              "from": "0", "size": "100"})
                        upper_coin = coin.upper()

                        if suc:
                            if data['data']:
                                coin_info = data['data'][0]
                                coin_addrs[upper_coin] = coin_info['address']

                                if coin_info['currency'] == 'xrp' or coin_info['currency'] == 'xmr' or coin_info['currency'] == 'eos':
                                    coin_addrs[upper_coin + 'TAG'] = coin_info['address-tag']

                            else:
                                coin_addrs[upper_coin] = ''

                    return True, coin_addrs, '', 0
            except Exception as ex:
                return False, '', '[Huobi]주소를 가져오는데 실패했습니다. [{}]'.format(ex), 1
        else:
            return False, '', '[Huobi]사용가능한 코인을 가져오는데 실패했습니다. [{}]'.format(gac_msg), 1

    async def balance(self):
        async with aiohttp.ClientSession(headers=self.get_headers) as sync:
            params = {'account-id': self.account_id}

            suc, data, msg, times = await self.async_api_request(
                                            sync,
                                            'GET',
                                            '/v1/account/accounts/{}/balance'.format(self.account_id),
                                            params)

            if suc:
                balance = {}
                for info in data['data']['list']:
                    if info['type'] == 'trade':

                        if float(info['balance']) > 0:
                            balance[info['currency'].upper()] = float(info['balance'])

                return suc, balance, msg, times

            else:
                return False, '', '[Huobi]지갑 값을 가져오는데 실패했습니다. [{}]'.format(msg)

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):  # 상위 평균매도/매수가 구함
        avg_order_book = {}
        async with aiohttp.ClientSession(headers=self.get_headers) as sync:
            try:
                for currency_pair in coin_list:
                    if currency_pair == 'BTC_BTC':
                        continue

                    convert = currency_pair.split('_')
                    coin = convert[1] + convert[0]

                    avg_order_book[currency_pair] = {}

                    params = {'symbol': coin.lower(), 'type': 'step0'}
                    suc, data, msg, times = await self.async_http_request(sync, 'GET', self._endpoint + '/market/depth', params)

                    if suc:
                        book = data['tick']
                        for types in ['asks', 'bids']:
                            order_amount, order_sum = 0, 0

                            info = book[types]
                            for order_data in info:
                                order_amount += Decimal(order_data[1])
                                order_sum += (Decimal(order_data[0]) * Decimal(order_data[1])).quantize(Decimal(10) ** -8)

                                if order_sum >= Decimal(btc_sum):
                                    calc = ((order_sum / order_amount).quantize(Decimal(10) ** -8))
                                    avg_order_book[currency_pair][types] = calc
                                    break

                    else:
                        return False, '', '[Huobi]마켓의 과거 코인가격을 가져오는데 실패했습니다. [{}]'.format(msg), times

                return True, avg_order_book, '', 0

            except Exception as ex:
                return False, '', '[Huobi]상위 평균매매가를 가져오는데 실패했습니다. [{}]'.format(ex), 1

    async def compare_orderbook(self, other, coins, default_btc=1):
        for _ in range(3):
            huobi_res, other_res = await asyncio.gather(
                self.get_curr_avg_orderbook(coins, default_btc),
                other.get_curr_avg_orderbook(coins, default_btc)
            )

            huobi_suc, huobi_avg_orderbook, huobi_msg, huobi_times = huobi_res
            other_suc, other_avg_orderbook, other_msg, other_times = other_res

            if 'BTC' in coins:
                # 나중에 점검
                coins.remove('BTC')

            if huobi_suc and other_suc:
                m_to_s = {}
                for currency_pair in coins:
                    m_ask = huobi_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in coins:
                    m_bid = huobi_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                res = huobi_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m}

                return True, res, '', 0

            else:
                time.sleep(huobi_times)
                continue

        if not huobi_suc or not other_suc:
            return False, '', 'huobi_error-[{}] other_error-[{}]'.format(huobi_msg, other_msg), huobi_times

