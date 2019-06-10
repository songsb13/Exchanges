import requests
import logging
import hmac
import hashlib
import base64
import urllib
import pycurl
import json
import time
import math
import certifi
import re
from bs4 import BeautifulSoup
from decimal import Decimal
logger = logging.getLogger(__name__)
debugger = logging.getLogger('Debugger')

class ErrorCode(Exception):
    def __init__(self, status, msg):
        self.code = status
        self.msg = msg

    def __str__(self):
        codelist = {
            5100: 'Bad Request',
            5200: 'Not Member',
            5300: 'Invalid ApiKey',
            5302: 'Method Not Allowed',
            5400: 'Database Fail',
            5500: 'Invalid Parameter',
            5600: 'CUSTOM NOTICE',
            5900: 'Unknown Error'
        }
        return "[{code}] {err_content}: {msg}".format(
            code=self.code, err_content=codelist[self.code], msg=self.msg)


class Bithumb:
    def __init__(self, __key, __secret):
        self.api_url = "https://api.bithumb.com"
        self.__key = __key
        self.__secret = __secret
        self.contents = b''
        self.transaction_fee = None

    def http_body_callback(self, buf):
        self.contents += buf

    def microtime(self, get_as_float=False):
        url = 'http://api.timezonedb.com/v2/get-time-zone?key=8HPR9HIM68XT&format=json&by=zone&zone=Asia/Seoul'
        while True:
            try:
                r = requests.get(url)
                t = r.json()
                break
            except:
                time.sleep(1)
        if get_as_float:
            return time.time()
        else:
            return '%f %d' % (math.modf(time.time())[0], t['timestamp'] - t['gmtOffset'])
        # if get_as_float:
        #     return time.time()
        # else:
        #     return '%f %d' % (math.modf(time.time()))

    def microsectime(self):
        mt = self.microtime(False)
        mt_array = mt.split(" ")[:2]
        return mt_array[1] + mt_array[0][2:5]

    def xcoinApiCall(self, endpoint, rgParams):
        # 1. Api-Sign and Api-Nonce information generation.
        # 2. Request related information from the Bithumb API server.
        #
        # - nonce: it is an arbitrary number that may only be used once. (Microseconds)
        # - api_sign: API signature information created in various combinations values.
        debugger.debug('Bithumb-Trading API[{}, {}]'.format(endpoint, rgParams))

        endpoint_item_array = {
            "endpoint": endpoint
        }

        uri_array = dict(endpoint_item_array, **rgParams)  # Concatenate the two arrays.

        e_uri_data = urllib.parse.urlencode(uri_array)

        # Api-Nonce information generation.
        nonce = self.microsectime()
        # debugger.debug("Nonce: {}".format(nonce))

        # Api-Sign information generation.
        hmac_key = self.__secret
        utf8_hmac_key = hmac_key.encode('utf-8')

        hmac_data = endpoint + chr(0) + e_uri_data + chr(0) + nonce
        utf8_hmac_data = hmac_data.encode('utf-8')

        hmh = hmac.new(bytes(utf8_hmac_key), utf8_hmac_data, hashlib.sha512)
        hmac_hash_hex_output = hmh.hexdigest()
        utf8_hmac_hash_hex_output = hmac_hash_hex_output.encode('utf-8')
        utf8_hmac_hash = base64.b64encode(utf8_hmac_hash_hex_output)

        api_sign = utf8_hmac_hash
        utf8_api_sign = api_sign.decode('utf-8')

        # Connects to Bithumb API server and returns JSON result value.
        curl_handle = pycurl.Curl()
        curl_handle.setopt(pycurl.CAINFO, certifi.where().encode())

        curl_handle.setopt(pycurl.POST, 1)
        # curl_handle.setopt(pycurl.VERBOSE, 1) # vervose mode :: 1 => True, 0 => False
        curl_handle.setopt(pycurl.POSTFIELDS, e_uri_data)

        url = self.api_url + endpoint
        curl_handle.setopt(curl_handle.URL, url)
        curl_handle.setopt(curl_handle.HTTPHEADER,
                           ['Api-Key: ' + self.__key, 'Api-Sign: ' + utf8_api_sign, 'Api-Nonce: ' + nonce])
        curl_handle.setopt(curl_handle.WRITEFUNCTION, self.http_body_callback)
        curl_handle.perform()

        # response_code = curl_handle.getinfo(pycurl.RESPONSE_CODE) # Get http response status code.

        curl_handle.close()

        try:
            ret_data = json.loads(self.contents.decode())
        except:
            print('')
        self.contents = b''

        debugger.debug('Bithumb-Trading API[{}, {}]-{}'.format(endpoint, rgParams, ret_data))
        return ret_data

    def orderbook(self):
        url = 'https://api.bithumb.com/public/orderbook/ALL'
        while True:
            try:
                response = requests.get(url)
                ret_data = response.json()['data']
                break
            except json.JSONDecodeError:
                time.sleep(3)
        del ret_data['payment_currency']
        del ret_data['timestamp']
        debugger.debug(ret_data)
        return ret_data

    def trade(self, buy, extra_params):
        """
        :param kwargs:
        currency(String): BTC, ETH, ...
        units(Float): 주문수량
        - 1회 최소 수량 (BTC: 0.001 | ETH: 0.01 | DASH: 0.01 | LTC: 0.1 | ETC: 0.1 | XRP: 10 | BCH: 0.01 | XMR: 0.01 | ZEC: 0.001 | QTUM: 0.1)
        - 1회 최대 수량 (BTC: 300 | ETH: 2,500 | DASH: 4,000 | LTC: 15,000 | ETC: 30,000 | XRP: 2,500,000 | BCH: 1,200 | XMR: 10,000 | ZEC: 2,500 | QTUM: 30,000)
        price(Int): KRW / 1 Currency
        type(String): bid(구매) / ask(판매)
        :return:
        """
        # params = {
        #     'apiKey': self.__key,
        #     'secretKey': self.__secret
        # }
        # params.update(kwargs)
        # url = 'https://api.bithumb.com/trade/market_buy'
        # response = requests.post(url, data=params)
        if buy:
            res = self.xcoinApiCall('/trade/market_buy', extra_params)
        else:
            res = self.xcoinApiCall('/trade/market_sell', extra_params)

        return res

    def get_balance(self):
        """
        Bithumb에는 currency를 ALL로 설정하여 balance를 볼 수 있다!
        :return:
        """
        while True:
            res = self.xcoinApiCall('/info/balance', {'currency': 'ALL'})
            try:
                ret_data = {key.split('_')[1].upper(): float(res['data'][key]) for key in res['data'] if
                            key.startswith('available') and float(res['data'][key]) > 0}
                break
            except:
                debugger.info('[Bithumb 잔고조회 실패] {}'.format(res))
                time.sleep(60)

        return ret_data

    def withdraw(self, coin, amount, to_address, payment_id=None):
        params = {
            'currency': coin,
            'units': amount,
            'address': to_address
        }
        if coin == 'XMR' or coin == 'XRP':
            params.update({'destination': payment_id})

        res = self.xcoinApiCall('/trade/btc_withdrawal', params)

        return res

    async def get_curr_avg_orderbook(self, currency_pair=None, amount=1):
        ret = {}
        data = self.orderbook()
        btc_avg = {}
        for order_type in ['bids', 'asks']:
            rows = data['BTC'][order_type]
            total_price = Decimal(0.0)
            total_amount = Decimal(0.0)
            for row in rows:
                total_price += Decimal(row['price']) * Decimal(row['quantity'])
                total_amount += Decimal(row['quantity'])

                if total_amount >= amount:
                    break

            btc_avg[order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)

        del data['BTC']

        for c in data:
            ret['BTC_'+c.upper()] = {}
            for order_type in ['bids', 'asks']:
                rows = data[c][order_type]
                total_price = Decimal(0.0)
                total_amount = Decimal(0.0)
                for row in rows:
                    if order_type == 'bids':
                        total_price += Decimal(row['price']) / btc_avg['asks'] * Decimal(row['quantity'])
                    else:
                        total_price += Decimal(row['price']) / btc_avg['bids'] * Decimal(row['quantity'])
                    total_amount += Decimal(row['quantity'])

                    if total_price >= amount:
                        break

                ret['BTC_'+c.upper()][order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)

        return ret

    def get_orderbook(self, intersecting_coins):
        order_book = self.orderbook()
        bids = {}
        asks = {}
        min_qty = {}
        for coin in intersecting_coins:
            if coin in order_book:
                bids[coin] = float(order_book[coin]['bids'][0]['price'].replace(',', ''))
                asks[coin] = float(order_book[coin]['asks'][0]['price'].replace(',', ''))
                min_qty[coin] = min([float(order_book[coin]['bids'][0]['quantity'].replace(',', '')),
                                     float(order_book[coin]['asks'][0]['quantity'].replace(',', ''))])

        return {'bids': bids, 'asks': asks, 'min_qty': min_qty}

    def get_available_coin(self):
        return [
            'BTC_ETH',
            'BTC_DASH',
            'BTC_LTC',
            'BTC_ETC',
            'BTC_XRP',
            'BTC_BCH',
            'BTC_XMR',
            'BTC_ZEC',
            'BTC_QTUM',
            'BTC_BTG',
            'BTC_EOS'
        ]

    def get_trading_fee(self):
        while True:
            res = self.xcoinApiCall('/info/account', {'currency': 'BTC'})
            try:
                ret_data = res['data']['trade_fee']
                break
            except:
                debugger.info('[Bithumb 거래 수수료 조회 실패] {}'.format(res))
                time.sleep(10)

        return Decimal(ret_data)

    def get_transaction_fee(self):
        while True:
            try:
                ret = requests.get('https://www.bithumb.com/u1/US138', timeout=60)
                soup = BeautifulSoup(ret.text, "lxml")
                tags = soup.find('table', 'g_table_list fee_in_out').find_all('tr')
                break
            except:
                try:
                    debugger.info('[Bithumb 이체 수수료 조회 실패] {}'.format(ret.text))
                except:
                    debugger.info('[Bithumb 이체 수수료 조회 실패] requests failed')

                if self.transaction_fee is not None:
                    last_retrieve_time = time.time()
                    return self.transaction_fee, last_retrieve_time

        ret_data = {}
        for tag in tags[3:]:
            key = re.search('[A-Z]+', tag.find('td', 'money_type').text).group()
            try:
                val = tag.find('div', 'right out_fee').text
                ret_data[key] = Decimal(val)
            except AttributeError:
                debugger.info('[{}] 출금 수수료를 찾을 수 없습니다.'.format(key))

        self.transaction_fee = ret_data
        last_retrieve_time = time.time()

        return ret_data, last_retrieve_time

    def get_deposit_addrs(self):
        ret_data = {}
        for currency in self.get_available_coin()+['BTC_BTC']:
            currency = currency[4:]
            while True:
                res = self.xcoinApiCall('/info/wallet_address', {'currency': currency})
                if res['status'] == '0000':
                    break
                else:
                    debugger.info('[Bithumb 입금 주소 조회 실패] {}'.format(res))
                    time.sleep(60)

            if currency == 'XRP':
                address, tag = res['data']['wallet_address'].split('&dt=')
                ret_data['XRPTAG'] = tag
                ret_data[currency] = address
            else:
                ret_data[currency] = res['data']['wallet_address']

        return ret_data

    def get_ticker(self, intersecting_coins):
        while True:
            try:
                res = requests.get('https://api.bithumb.com/public/ticker/ALL')
                debugger.debug('Bithumb - Ticker - {}'.format(res.text))
                j_res = res.json()
                if res.status_code == 200 and 'data' in j_res:
                    break
                else:
                    time.sleep(1)
            except:
                time.sleep(1)

        ret = {}
        for key, val in j_res['data'].items():
            if 'closing_price' in val and key.upper() in intersecting_coins:
                ret[key] = int(val['closing_price'])
        return ret

