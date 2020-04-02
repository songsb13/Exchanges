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
import asyncio
import requests
from urllib.parse import urlencode

bithumb_logger = logging.getLogger(__name__)
bithumb_logger.setLevel(logging.DEBUG)

fmt = logging.Formatter('[%(asctime)s - %(lineno)d] %(message)s')
f_hdlr = logging.FileHandler('bithumb.log')
f_hdlr.setLevel(logging.DEBUG)
f_hdlr.setFormatter(fmt)

s_hdlr = logging.StreamHandler()
s_hdlr.setLevel(logging.INFO)
s_hdlr.setFormatter(fmt)

bithumb_logger.addHandler(f_hdlr)
bithumb_logger.addHandler(s_hdlr)


class WrongOutputReceived(Exception):
    pass


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
    NAME = 'Bithumb'

    def __init__(self, __key, __secret):
        self.api_url = "https://api.bithumb.com"
        self._key = __key
        self._secret = __secret
        self.contents = b''
        self.transaction_fee = None

    def public_call(self, endpoint, extra_params={}):
        bithumb_logger.debug("Bithumb Public {} 호출시도".format(endpoint))
        try:
            if extra_params:
                data = urlencode(extra_params)
                response = requests.get(self.api_url + endpoint, data=data)
            else:
                response = requests.get(self.api_url + endpoint)
        except:
            bithumb_logger.debug("Bithumb Public API 호출실패!!")
            return None
        try:
            result = response.json()
            bithumb_logger.debug("Bithumb Public API 호출 결과: {}".format(result))
            return result
        except:
            bithumb_logger.debug("Bithumb Public API 결과값 이상: {}".format(response.text))
            return None

    def private_call(self, endpoint, extra_params={}):
        extra_params.update({'endpoint': endpoint})

        nonce = str(int(time.time() * 1000))
        data = urlencode(extra_params)
        hmac_data = endpoint + chr(0) + data + chr(0) + nonce
        hashed = hmac.new(self._secret.encode('utf-8'), hmac_data.encode('utf-8'), hashlib.sha512).hexdigest()
        signature = base64.b64encode(hashed.encode('utf-8')).decode('utf-8')

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Api-Key': self._key,
            'Api-Sign': signature,
            'Api-Nonce': nonce
        }

        try:
            bithumb_logger.debug("Bithumb Private {} 호출시도".format(endpoint))
            response = requests.post(self.api_url + endpoint, headers=headers, data=data)
        except:
            bithumb_logger.debug("Bithumb Private API 호출실패!!")
            return None

        try:
            result = response.json()
            bithumb_logger.debug("Bithumb Private API 호출 결과: {}".format(result))
            return result
        except:
            bithumb_logger.debug("Bithumb Private API 결과값 이상: {}".format(response.text))
            return None

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
        bithumb_logger.debug('Bithumb-Trading API[{}, {}]'.format(endpoint, rgParams))
        endpoint_item_array = {
            "endpoint": endpoint
        }

        uri_array = dict(endpoint_item_array, **rgParams)  # Concatenate the two arrays.

        e_uri_data = urllib.parse.urlencode(uri_array)

        # Api-Nonce information generation.
        nonce = self.microsectime()
        # bithumb_logger.debug("Nonce: {}".format(nonce))

        # Api-Sign information generation.
        hmac_key = self._secret
        utf8_hmac_key = hmac_key.encode('utf-8')

        hmac_data = endpoint + chr(0) + e_uri_data + chr(0) + nonce
        utf8_hmac_data = hmac_data.encode('utf-8')

        hmh = hmac.new(bytes(utf8_hmac_key), utf8_hmac_data, hashlib.sha512)
        hmac_hash_hex_output = hmh.hexdigest()
        utf8_hmac_hash_hex_output = hmac_hash_hex_output.encode('utf-8')
        utf8_hmac_hash = base64.b64encode(utf8_hmac_hash_hex_output)

        api_sign = utf8_hmac_hash
        utf8_api_sign = api_sign.decode('utf-8')

        try:
            # Connects to Bithumb API server and returns JSON result value.
            self.contents = b''
            curl_handle = pycurl.Curl()
            curl_handle.setopt(pycurl.CAINFO, certifi.where().encode())

            curl_handle.setopt(pycurl.POST, 1)
            # curl_handle.setopt(pycurl.VERBOSE, 1) # vervose mode :: 1 => True, 0 => False
            curl_handle.setopt(pycurl.POSTFIELDS, e_uri_data)

            url = self.api_url + endpoint
            curl_handle.setopt(curl_handle.URL, url)
            curl_handle.setopt(curl_handle.HTTPHEADER,
                               ['Api-Key: ' + self._key, 'Api-Sign: ' + utf8_api_sign, 'Api-Nonce: ' + nonce])
            curl_handle.setopt(curl_handle.WRITEFUNCTION, self.http_body_callback)
            curl_handle.perform()

            # response_code = curl_handle.getinfo(pycurl.RESPONSE_CODE) # Get http response status code.

            curl_handle.close()
        except:
            bithumb_logger.debug("CURL FAILED")
            bithumb_logger.info("{} 에서 잘못된 응답을 받았습니다.".format(endpoint))
            return False, None, "{} 에서 잘못된 응답을 받았습니다.".format(endpoint), 3


        # try:
        ret_data = json.loads(self.contents.decode())
        # except:
        #     bithumb_logger.exception(self.contents.decode())
        #     bithumb_logger.info("{} 에서 잘못된 응답을 받았습니다. 다시 시도합니다.".format(endpoint))
        #     time.sleep(30)
        #     continue

        bithumb_logger.debug('Bithumb-Trading API[{}, {}]-{}'.format(endpoint, rgParams, ret_data))

        if 'data' not in ret_data:
            sleep_time = 5
            if 'message' in ret_data and '최소' in ret_data['message']:
                sleep_time = 0

            return False, ret_data, ret_data['message'] if 'message' in ret_data else '', sleep_time

        return True, ret_data, '', 0

    def orderbook(self):
        bithumb_logger.debug('Bithumb-Public API[orderbook, ALL]')
        url = 'https://api.bithumb.com/public/orderbook/ALL'
        while True:
            try:
                response = requests.get(url)
                bithumb_logger.debug('Bithumb-Public API[orderbook, ALL]-{}'.format(response.json()))
                ret_data = response.json()['data']
                break
            except json.JSONDecodeError:
                time.sleep(3)
            except KeyError:
                bithumb_logger.debug('{}'.format(response.json()))
                time.sleep(3)
            except Exception as e:
                bithumb_logger.debug(str(e))
                time.sleep(3)

        del ret_data['payment_currency']
        del ret_data['timestamp']
        bithumb_logger.debug(ret_data)
        return ret_data

    def trade(self, buy, extra_params):
        """
        :param buy:
        True: bid(구매)
        False: ask(판매)

        :param extra_params:
        currency(String): BTC, ETH, ...
        units(Float): 주문수량
        - 1회 최소 수량 (BTC: 0.001 | ETH: 0.01 | DASH: 0.01 | LTC: 0.1 | ETC: 0.1 | XRP: 10 | BCH: 0.01 | XMR: 0.01 | ZEC: 0.001 | QTUM: 0.1)
        - 1회 최대 수량 (BTC: 300 | ETH: 2,500 | DASH: 4,000 | LTC: 15,000 | ETC: 30,000 | XRP: 2,500,000 | BCH: 1,200 | XMR: 10,000 | ZEC: 2,500 | QTUM: 30,000)
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

    def buy(self, extra_params):
        return self.xcoinApiCall('/trade/market_buy', extra_params)

    def sell(self, extra_params):
        return self.xcoinApiCall('/trade/market_sell', extra_params)

    def ticker(self, currency='ALL'):
        result = self.public_call('/public/ticker/' + currency)

        if not result:
            #   에러가 발생하여 None 이 Return 된 경우
            #   네트워크 에러 혹은 리턴결과가 json 형식이 아닐 경우에만 발생
            return False, None, "예외 발생", 5
            # raise WrongOutputReceived("Bithumb Sell 예외발생")
        elif result['status'] != '0000':
            #   결과는 나왔으나 에러코드가 발생한 경우
            return False, None, result['message'], 3
        else:
            #   혹시나 결과값을 이용할 일이 생길 때를 대비함
            return True, result, '', 0

    def balance(self):
        """
        Bithumb에는 currency를 ALL로 설정하여 balance를 볼 수 있다!
        :return:
        """
        try:
            success, res, msg, sleep_time = self.xcoinApiCall('/info/balance', {'currency': 'ALL'})
        except:
            bithumb_logger.info('[Bithumb 잔고조회 실패] Cloudflare Failed')
            return False, None, '[Bithumb 잔고조회 실패] Cloudflare Failed', 60

        if 'message' in res and 'Invalid' in res['message']:
            return False, None, res['message'], 0

        try:
            ret_data = {key.split('_')[1].upper(): float(res['data'][key]) for key in res['data'] if
                        key.startswith('available') and float(res['data'][key]) > 0}
        except:
            bithumb_logger.info('[Bithumb 잔고조회 실패] {}'.format(res))
            return False, None, res['message'], 60

        return True, ret_data, '', 0

    def withdraw(self, coin, amount, to_address, payment_id=None):
        params = {
            'currency': coin,
            'units': amount,
            'address': to_address
        }
        if coin == 'XMR' or coin == 'XRP':
            params.update({'destination': payment_id})

        res = self.xcoinApiCall('trade/btc_withdrawal', params)

        return res

    def get_curr_avg_orderbook(self, amount=1):
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

                if total_amount >= Decimal(amount):
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

                    if total_price >= Decimal(amount):
                        break

                ret['BTC_'+c.upper()][order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)

        return ret

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

    async def get_trading_fee(self):
        success, res, msg, sleep_time = self.xcoinApiCall('/info/account', {'currency': 'BTC'})
        try:
            ret_data = res['data']['trade_fee']
        except:
            bithumb_logger.info('[Bithumb 거래 수수료 조회 실패] {}'.format(res))
            return False, None, '거래 수수료 조회 실패', 10

        return True, float(ret_data), '', 0

    # def get_transaction_fee(self):
    #     while True:
    #         try:
    #             ret = requests.get('https://www.bithumb.com/u1/US138', timeout=60)
    #             soup = BeautifulSoup(ret.text, "html.parser")
    #             tags = soup.find('table', 'g_table_list fee_in_out').find_all('tr')
    #             break
    #         except:
    #             try:
    #                 bithumb_logger.info('[Bithumb 이체 수수료 조회 실패] {}'.format(ret.text))
    #             except:
    #                 bithumb_logger.info('[Bithumb 이체 수수료 조회 실패] requests failed')
    #
    #             if self.transaction_fee is not None:
    #                 return self.transaction_fee
    #
    #     ret_data = {}
    #     for tag in tags[3:]:
    #         key = re.search('[A-Z]+', tag.find('td', 'money_type').text).group()
    #         val = tag.find('td', 'right').text
    #         ret_data[key] = float(val)
    #
    #     self.transaction_fee = ret_data
    #
    #     return ret_data
    def get_transaction_fee(self):
        while True:
            try:
                ret = requests.get('https://www.bithumb.com/u1/US138', timeout=60)
                soup = BeautifulSoup(ret.text, "lxml")
                tags = soup.find('table', 'g_table_list fee_in_out').find_all('tr')
                break
            except:
                try:
                    bithumb_logger.info('[Bithumb 이체 수수료 조회 실패] {}'.format(ret.text))
                except:
                    bithumb_logger.info('[Bithumb 이체 수수료 조회 실패] requests failed')

                if self.transaction_fee is not None:
                    return self.transaction_fee

        ret_data = {}
        for tag in tags[3:]:
            key = re.search('[A-Z]+', tag.find('td', 'money_type').text).group()
            try:
                val = tag.find('div', 'right out_fee').text
                ret_data[key] = float(val)
            except AttributeError:
                bithumb_logger.info('[{}] 출금 수수료를 찾을 수 없습니다.'.format(key))

        self.transaction_fee = ret_data
        last_retrieve_time = time.time()
        return ret_data

        # return ret_data, last_retrieve_time

    def get_precision(self, pair):
       return True, (-4, -4), '', 0

    def get_deposit_addrs(self):
        ret_data = {}
        for currency in self.get_available_coin()+['BTC_BTC']:
            currency = currency[4:]
            while True:
                res = self.xcoinApiCall('/info/wallet_address', {'currency': currency})
                if res['status'] == '0000':
                    break
                else:
                    bithumb_logger.info('[Bithumb 입금 주소 조회 실패] {}'.format(res))
                    time.sleep(60)

            if currency == 'XRP':
                address, tag = res['data']['wallet_address'].split('&dt=')
                ret_data[currency + 'TAG'] = tag
                ret_data[currency] = address
            else:
                ret_data[currency] = res['data']['wallet_address']

        return ret_data

    async def bithumb__poloniex(self, polo, default_btc):
        poloniex_currency_pair = polo.tradable_currencies()
        bithumb_currency_pair = self.get_available_coin()

        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, self.get_curr_avg_orderbook, default_btc)
        bithumb_avg_orderbook = await fut

        fut = loop.run_in_executor(None, polo.get_curr_avg_orderbook, poloniex_currency_pair, default_btc)
        poloniex_avg_orderbook = await fut

        b_to_p = {}
        for currency_pair in bithumb_currency_pair:
            try:
                b_ask = bithumb_avg_orderbook[currency_pair]['asks']
                p_bid = poloniex_avg_orderbook[currency_pair]['bids']
                b_to_p[currency_pair] = float(((p_bid - b_ask) / b_ask).quantize(Decimal(10) ** -8))
            except KeyError:
                #   두 거래소 중 한쪽에만 있는 currency 일 경우 제외한다.
                continue

        p_to_b = {}
        for currency_pair in poloniex_currency_pair:
            try:
                b_bid = bithumb_avg_orderbook[currency_pair]['bids']
                p_ask = poloniex_avg_orderbook[currency_pair]['asks']
                p_to_b[currency_pair] = float(((b_bid - p_ask) / b_bid).quantize(Decimal(10) ** -8))
            except KeyError:
                #   위와 동일
                continue

        for key in bithumb_avg_orderbook.keys():
            for key2 in ['bids', 'asks']:
                bithumb_avg_orderbook[key][key2] = float(bithumb_avg_orderbook[key][key2].quantize(Decimal(10) ** -8))
                #   json 으로 전송하기 위해 Decimal을 float으로 바꿔줌
        for key in poloniex_avg_orderbook.keys():
            for key2 in ['bids', 'asks']:
                poloniex_avg_orderbook[key][key2] = float(poloniex_avg_orderbook[key][key2].quantize(Decimal(10) ** -8))

        return {'b_to_p': b_to_p, 'p_to_b': p_to_b, 'b_o_b': bithumb_avg_orderbook, 'p_o_b': poloniex_avg_orderbook}

if __name__ == '__main__':
    # {'secret': 'e2fbc69806679ccb599ff8910a51cf55', 'key': '66532396a269f0af7212fc5869bfc79d'},
    # bit = Bithumb('5921ef4e1e53622c4d46f827e3fcb527', '687d509dbaeaa2a01675bed46e629551')
    bit = Bithumb('66532396a269f0af7212fc5869bfc79d', 'e2fbc69806679ccb599ff8910a51cf55')
    a = bit.balance()
    print(bit.get_trading_fee())
    print(bit.get_transaction_fee())
    pass