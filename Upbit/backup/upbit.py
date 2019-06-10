import sys
import hmac
import hashlib
import requests
import json
import logging
from urllib.parse import urlencode
from datetime import datetime
from decimal import *
import asyncio
import base64
import time
import configparser
import aiohttp
import jwt
import numpy as np
import re
from selenium import webdriver

upbit_logger = logging.getLogger(__name__)
upbit_logger.setLevel(logging.DEBUG)

f_hdlr = logging.FileHandler('upbit_logger.log')
s_hdlr = logging.StreamHandler()

upbit_logger.addHandler(f_hdlr)
upbit_logger.addHandler(s_hdlr)
cfg = configparser.ConfigParser()
cfg.read('Settings.ini')

driver_path = '../chromedriver.exe'


class BaseUpbit:
    def __init__(self, key, secret):
        self.endpoint = 'https://api.upbit.com/v1'

        self.key = key
        self.secret = secret
        self.client = None
        self.client_secret = None

    def jwt(self):
        # transactionFee 구하기 위해 가져와야하는 값임.
        if not self.client and not self.client_secret:
            return False, '', 'Client와 Cleint키가 설정이 되어있지 않습니다.', 1

        sig1 = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        sig2 = base64.b64encode(
            json.dumps({'access_key': self.client, 'nonce': int(time.time() * 1000)}).replace(' ',
                                                                                              '').encode()).decode()
        sig2 = re.sub("=+", "", sig2.replace('/', '_').replace('+', '-'))
        signature = base64.b64encode(
            hmac.new(self.client_secret.encode(), (sig1 + '.' + sig2).encode(), hashlib.sha256).digest()).decode()

        signature = re.sub("=+", "", signature.replace('/', '_').replace('+', '-'))

        ret = sig1 + "." + sig2 + "." + signature

        return True, ret, '', 0

    def decrypt_token(self, token):
        # transactionFee 구하기 위해 가져와야하는 값임.

        try:
            tk = json.loads(token)
            payload = tk['accessToken'].split('.')
            pair = json.loads(base64.b64decode(payload[1] + '==').decode())['api']
            self.client = pair['access_key']
            self.client_secret = pair['secret_key']

            upbit_logger.info("JWT Client: {}".format(self.client))
            upbit_logger.info("JWT Secret: {}".format(self.client_secret))

            res = {
                'client': self.client,
                'secret': self.client_secret
            }

            return True, res, '', 0

        except:
            return False, '', '', 1

    def login(self, mail, pw):
        try:
            driver = webdriver.Chrome(driver_path)
            driver.implicitly_wait(30)

            driver.get('https://upbit.com/signin')

            login_session = driver.find_element_by_class_name('btnKakao').get_attribute('href')

            driver.get(login_session)

            id_box = driver.find_element_by_id('loginEmail')
            pw_box = driver.find_element_by_id('loginPw')

            for box in [id_box, pw_box]:
                box.clear()

            id_box.send_keys(mail)
            pw_box.send_keys(pw)

            driver.find_element_by_xpath('//button[contains(@class, "btn_login")]').click()

            driver.implicitly_wait(10)

            try:
                driver.find_element_by_class_name('recaptcha-checkbox-checkmark').click()
                driver.find_element_by_xpath('//button[contains(@class, "btn_login")]').click()

            except:
                upbit_logger.debug('캡챠 코드가 발생하지 않았습니다.')

            driver.implicitly_wait(30)

            auth = input('카카오 인증코드를 입력하세요: ')
            driver.find_element_by_xpath('//input[@class="txt"]').send_keys(auth + '\n')

            cookies = driver.get_cookie('tokens')['value']

            return True, cookies, '', 0

        except:
            return False, '', '로그인에 실패했습니다.', 10

    def public_api(self, method, path, extra=None, header=None):
        url = '/'.join([self.endpoint, path])

        if header is None:
            header = {}

        if extra is None:
            extra = {}

        if method.lower() == 'post':
            rq = requests.post(url, headers=header, json=extra)
        else:
            # method == get/put/delete
            rq = requests.request(method, url, headers=header, params=extra)

        try:
            res = rq.json()

            if 'error' in res:
                return False, '', '값을 가져오는데 실패했습니다. [{}]'.format(res['error']['message']), 1

            else:
                return True, res, '', 0

        except Exception as ex:
            return False, '', '서버와 통신에 실패했습니다. [{}]'.format(ex), 1

    def private_api(self, method, path, extra=None):
        payload = {
            'access_key': self.key,
            'nonce': int(time.time() * 1000),
        }

        if extra is not None:
            payload.update({'query': urlencode(extra)})

        jwt_token = jwt.encode(payload, self.secret, ).decode('utf8')
        authorization_token = 'Bearer {}'.format(jwt_token)
        private_header = {'Authorization': authorization_token}

        suc, data, msg, time_ = self.public_api(method, path, extra, private_header)

        return suc, data, msg, time_

    def ticker(self, markets):
        markets = markets.replace('_', '-')
        market = {'markets': markets}
        tic_suc, tic_data, tic_msg, tic_time = self.public_api('get', 'ticker', market)

        if not tic_suc:
            return False, '', tic_msg, tic_time

        else:
            trade_price = tic_data[0]['trade_price']

            return True, trade_price, tic_msg, tic_time

    def service_currencies(self):
        # Deposit_addrs를 쓸 때 사용함. 모든 코인값과 중복 값을 제거해야하므로 분리
        cur_suc, cur_data, cur_msg, cur_time = self.public_api('get', '/'.join(['market', 'all']))

        if not cur_suc:
            return False, '', cur_msg, cur_time

        res = []
        for data in cur_data:
            currency = data['market'].split('-')[1]
            if currency not in res:
                res.append(currency)

        return True, res, '', 0

    def currencies(self):
        # 각 클래스에서 처리가 될 KRW-BTC 같은 형식의 값을 리턴함
        cur_suc, cur_data, cur_msg, cur_time = self.public_api('get', '/'.join(['market', 'all']))

        if not cur_suc:
            return False, '', cur_msg, cur_time

        res = []
        [res.append(data['market']) for data in cur_data if not data['market'] in res]

        return True, res, '', 0

    def get_precision(self, pair):
        return True, (-8, -8), '', 0

    def fee_count(self):
        # 몇변의 수수료가 산정되는지
        return 1

    def withdraw(self, coin, amount, to_address, payment_id=None):
        upbit_logger.debug('출금-[{}][{}][{}][{}] 받았습니다.'.format(coin, amount, to_address, payment_id))

        params = {
                    'currency': coin,
                    'address': to_address,
                    'amount': '{}'.format(amount),
                }

        if payment_id:
            tag_dic = {'secondary_address': payment_id}
            params.update(tag_dic)

        local_path = '/'.join(['withdraws', 'coin'])
        suc, data, msg, time_ = self.private_api('post', local_path, params)

        if not suc:
            return False, '', '[Upbit] 출금 중 에러가 발생했습니다. = [{}]'.format(msg)

        return suc, data, msg, time_

    def get_candle(self, coin, unit, count):
        # 1, 3, 5, 15, 10, 30, 60, 240 분이 가능함.

        coin = coin.replace('_', '-')

        path = '/'.join(['candles', 'minutes', str(unit)])

        params = {'market': coin, 'count': count}

        suc, data, msg, time_ = self.public_api('get', path, params)

        if 'err-msg' in data or not suc:
            return False, 'Fail', data['err-msg']

        coin_history = {}
        coin_history['open'] = []
        coin_history['high'] = []
        coin_history['low'] = []
        coin_history['close'] = []
        coin_history['volume'] = []
        coin_history['timestamp'] = []

        for info in data:  # 리스트가 늘어날 수도?
            coin_history['open'].append(info['opening_price'])
            coin_history['high'].append(info['high_price'])
            coin_history['low'].append(info['low_price'])
            coin_history['close'].append(info['trade_price'])
            coin_history['volume'].append(info['candle_acc_trade_volume'])
            coin_history['timestamp'].append(info['candle_date_time_kst'])

        return True, coin_history, ''

    def get_order_history(self, uuid):
        params = {
            'uuid': uuid
        }

        suc, data, msg, time_ = self.private_api('get', 'order', params)

        if not suc:
            return False, '', msg

        if not data['trades']:
            # 처음에 바로 받아올 때 빈 리스트를 받는 경우가 있다
            # 2번째 가져올때는 가져와지는듯함( 테스트했을 때)
            return False, '', 'Trade에 빈 리스트가 반환되었습니다.'

        return True, data, ''


    async def async_public_api(self, method, path, extra=None, header=None):
        if header is None:
            header = {}

        if extra is None:
            extra = {}

        path = '/'.join([self.endpoint, path])
        async with aiohttp.ClientSession(headers=header) as s:
            if method.lower() == 'post':
                rq = await s.post(path, json=extra)

            else:  # elif method.lower() == 'get':
                rq = await s.get(path, params=extra)

            try:
                rq = await rq.text()
                res = json.loads(rq)

                if 'error' in res:
                    return False, '', '값을 가져오는데 실패했습니다. [{}]'.format(res['error']['message']), 1

                else:
                    return True, res, '', 0

            except Exception as ex:
                return False, '', '서버와 통신에 실패했습니다. [{}]'.format(ex), 1

    async def async_private_api(self, method, path, extra=None):
        payload = {
            'access_key': self.key,
            'nonce': int(time.time() * 1000),
        }

        if extra is not None:
            payload.update({'query': urlencode(extra)})

        jwt_token = jwt.encode(payload, self.secret, ).decode('utf8')
        authorization_token = 'Bearer {}'.format(jwt_token)
        header = {'Authorization': authorization_token}

        suc, data, msg, time_ = await self.async_public_api(method, path, extra, header)

        return suc, data, msg, time_

    async def get_transation_fee(self):
        path = '/'.join(['withdraws', 'chance'])

        suc, currencies, msg, time_ = self.service_currencies()

        if not suc:
            return False, '', '[Upbit] 거래가능한 코인을 가져오는 중 에러가 발생했습니다. = [{}]'.format(msg), time_

        fees = {}
        for currency in currencies:
            ts_suc, ts_data, ts_msg, ts_time = await self.async_private_api('get', path, {'currency': currency})

            if not ts_suc:
                return False, '', '[Upbit] 출금 수수료를 가져오는 중 에러가 발생했습니다. = [{}]'.format(ts_msg), ts_time

            else:
                if ts_data['currency']['withdraw_fee'] is None:
                    ts_data['currency']['withdraw_fee'] = 0

                fees[currency] = Decimal(ts_data['currency']['withdraw_fee']).quantize(Decimal(10) ** -8)

        return True, fees, '', 0

    async def orderbook_calculator(self, coin_list, btc_sum):
        # 일반적인 BTC_XXX 값을 계산 할 때 쓰는 orderbook함수
        try:
            avg_order_book = {}
            for currency in coin_list:
                if currency == 'BTC_BTC':
                    continue

                api_currency = currency.replace('_', '-')
                dep_suc, book, dep_msg, dep_time = await self.async_public_api('get', 'orderbook', {'markets': api_currency})

                if not dep_suc:
                    return dep_suc, book, dep_msg, dep_time

                avg_order_book[currency] = {}
                for type_ in ['ask', 'bid']:
                    order_amount, order_sum = [], 0

                    for data in book[0]['orderbook_units']:
                        size = data['{}_size'.format(type_)]
                        order_amount.append(size)
                        order_sum += data['{}_price'.format(type_)] * size

                        if order_sum >= btc_sum:
                            volume = order_sum / np.sum(order_amount)
                            avg_order_book[currency]['{}s'.format(type_)] = Decimal(volume).quantize(Decimal(10) ** -8)

                            break

            return True, avg_order_book, '', 0
        except Exception as ex:
            return False, '', '[Upbit]Orderbook값을 가져오는 중 에러가 발생했습니다.[{}]'.format(ex), 1

    async def get_btc_orderbook(self, btc_sum):
        # krw계산 때 btc의 평균 값을 도출하기 위한 함수
        for _ in range(10):
            dep_suc, orderbook, dep_msg, dep_time = await self.async_public_api('get', 'orderbook',
                                                                                {'markets': 'KRW-BTC'
                                                                                 })
            if dep_suc:
                break
            else:
                time.sleep(dep_time)
        else:
            return False, '', dep_msg, dep_time

        btc_average_price = {}
        try:
            for type_ in ['ask', 'bid']:
                amount_sum, price_sum = 0, []

                for each in orderbook[0]['orderbook_units']:
                    price, amount = each['{}_price'.format(type_)], each['{}_size'.format(type_)]

                    amount_sum += Decimal(amount).quantize(Decimal(10) ** -8)
                    price_sum.append(int(price))
                    if amount_sum >= btc_sum:
                        btc_average_price['{}s'.format(type_)] = np.sum(price_sum) / len(price_sum)
                        break

            return True, btc_average_price, '', 0
        except Exception as ex:
            return False, '', '[Upbit]BTC값 계산중 에러가 발생했습니다 [{}]'.format(ex), 1

    async def get_krw_orderbook(self, coin_list, btc_average_price, btc_sum=1):
        # krw이 들어왔을 때 사용하는 함수
        try:
            total_coin_res = {}
            for currency in coin_list:
                api_currency = currency.replace('_', '-')
                for _ in range(10):
                    dep_suc, orderbook, dep_msg, dep_time = await self.async_public_api('get', 'orderbook',
                                                                                        {'markets': api_currency})
                    if dep_suc:
                        break
                    else:
                        time.sleep(dep_time)

                else:
                    return False, '', dep_msg, dep_time

                alt_res = {}
                for type_ in ['ask', 'bid']:
                    amount_sum, price_sum = 0, []

                    for each in orderbook[0]['orderbook_units']:
                        price, amount = each['{}_price'.format(type_)], each['{}_size'.format(type_)]

                        amount_sum += Decimal(amount).quantize(Decimal(10) ** -8)
                        price_sum.append(int(price))
                        if amount_sum >= btc_sum:
                            alt_average_price = np.sum(price_sum) / len(price_sum)
                            res = btc_average_price['{}s'.format(type_)] / alt_average_price

                            alt_res['{}s'.format(type_)] = Decimal(res).quantize(Decimal(10) ** -8)
                            break
                total_coin_res[currency] = alt_res

            return True, total_coin_res, '', 0
        except Exception as ex:
            return False, '', '[Upbit]평균가를 가져오는 중 에러가 발생했습니다. [{}]'.format(ex), 1

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        # BTC_XRP, ETH_KRW같은 값들이 같이 들어오는지 확인..
        if 'krw' in coin_list[0].lower():
            # KRW을 구하려는 경우 KRW전용으로 간다
            btc_suc, btc_average_price, btc_msg, btc_time = await self.get_btc_orderbook(btc_sum)
            if not btc_suc:
                return False, '', btc_msg, btc_time

            krw_suc, krw_total_res, krw_msg, krw_time = await self.get_krw_orderbook(coin_list, btc_average_price,
                                                                                     btc_sum)

            return krw_suc, krw_total_res, krw_msg, krw_time

        else:
            coin_suc, coin_total_res, coin_msg, coin_time = await self.orderbook_calculator(coin_list, btc_sum)

            return coin_suc, coin_total_res, coin_msg, coin_time

    async def get_deposit_addrs(self):
        # 출금주소
        res = {}
        try:
            suc, currencies, msg, time_ = self.service_currencies()
            if not suc:
                return False, '', msg, time_

            jwt_suc, token, jwt_msg, jwt_time = self.jwt()
            if not suc:
                return False, '', jwt_msg, jwt_time

            headers = {'Authorization': 'Bearer {}'.format(token)}

            async with aiohttp.ClientSession(headers=headers) as session:
                for coin in currencies:
                    param = {'currency': coin}
                    while True:
                        rq = await session.get('https://ccx.upbit.com/api/v1/deposits/coin_address', params=param)
                        rq = await rq.text()
                        data = json.loads(rq)
                        if 'error' in data and data['error']['name'] == 'V1::Exceptions::TooManyRequestCoinAddress':
                            continue
                        if 'deposit_address' in data.keys():
                            if '?dt=' in data['deposit_address']:
                                dt = data['deposit_address'].split('?dt=')
                                res[coin] = dt[0]
                                res[coin + 'TAG'] = dt[1]
                            else:
                                res[coin] = data['deposit_address']

                        break
            return True, res, '', 0
        except Exception as ex:
            return False, '', '[Upbit]입금주소를 가져오는 중 에러가 발생했습니다. [{}]'.format(ex), 1

    async def balance(self):
        try:
            bal_suc, bal_data, bal_msg, bal_time = await self.async_private_api('get', 'accounts')

            if not bal_suc:
                return False, '', bal_msg, bal_time

            res = {}
            for bal in bal_data:
                res[bal['currency']] = float(bal['balance'])

            return True, res, '', 0

        except Exception as ex:
            return False, '', '[Upbit]Balance 오류가 발생했습니다. [{}]'.format(ex)

    async def compare_orderbook(self, other, coins, default_btc=1):
        for _ in range(3):
            upbit_res, other_res = await asyncio.gather(
                self.get_curr_avg_orderbook(coins, default_btc),
                other.get_curr_avg_orderbook(coins, default_btc)
            )

            upbit_suc, upbit_avg_orderbook, upbit_msg, upbit_times = upbit_res
            other_suc, other_avg_orderbook, other_msg, other_times = other_res

            if 'BTC' in coins:
                # 나중에 점검
                coins.remove('BTC')

            if upbit_suc and other_suc:
                m_to_s = {}
                for currency_pair in coins:
                    m_ask = upbit_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in coins:
                    m_bid = upbit_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                res = upbit_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m}

                return True, res, '', 0

            else:
                time.sleep(upbit_times)
                continue

        if not upbit_suc or not other_suc:
            return False, '', '[Upbit]upbit_error-[{}] other_error-[{}]'.format(upbit_msg, other_msg), upbit_times


class UpbitBTC(BaseUpbit):
    def __init__(self, key, secret):
        super().__init__(key, secret)

    def fee_count(self):
        # 2? 1? 경우가 다름
        return 1

    def buy(self, coin, amount):
        upbit_logger.info('구매, Coin-[{}] Amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = coin.replace('_', '-')

        tic_suc, price, tic_msg, tic_time = self.ticker(coin)

        if not tic_suc:
            return False, '', tic_msg, tic_time

        params = {
            'market': coin,
            'side': 'bid',
            'volume': str(amount),
            'price': int(price) * 1.05,
            'ord_type': 'limit'
        }

        suc, data, msg, times = self.private_api('POST', 'orders', params)

        return suc, data, msg, times

    def sell(self, coin, amount):
        upbit_logger.info('판매, Coin-[{}] Amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = coin.replace('_', '-')

        tic_suc, price, tic_msg, tic_time = self.ticker(coin)

        if not tic_suc:
            return False, '', tic_msg, tic_time

        params = {
            'market': coin,
            'side': 'ask',
            'volume': str(amount),
            'price': int(price) * 0.95,
            'ord_type': 'limit'
        }
        suc, data, msg, times = self.private_api('POST', 'orders', params)

        return suc, data, msg, times

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        suc, data, msg, time_ = self.buy(currency_pair, alt_amount)

        if not suc:
            return False, '', '[Upbit]BaseToAlt실패 = [{}]'.format(msg), 0

        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return True, alt_amount, '', 0

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        for _ in range(10):
            suc, data, msg, time_ = self.sell(currency_pair, alt_amount)

            if suc:
                upbit_logger.info('AltToBase 성공')

                return True, '', data, 0

            else:
                upbit_logger.info(msg)

                if '부족합니다.' in msg:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue

        else:
            return False, '', '[Upbit]AltToBase실패 = [{}]'.format(msg)


class UpbitKRW(BaseUpbit):
    def __init__(self, key, secret):
        super().__init__(key, secret)

    def fee_count(self):
        # 2? 1? 경우가 다름
        return 2

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        # btc sell alt buy
        # alt = Decimal(alt_amount)
        for _ in range(10):
            suc, data, msg, time_ = self.sell('BTC', btc_amount)
            if suc:
                upbit_logger.info('BaseToAlt BTC판매 성공')
                break

            else:
                upbit_logger.info(msg)

                if '부족합니다.' in msg:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
        else:
            return False, '', '[Upbit]BaseToAlt실패 = [{}]'.format(msg)

        # currency_pair가 BTC_XRP 형식?
        currency_pair = currency_pair.split('_')[1]

        for _ in range(10):
            suc, data, msg, time_ = self.buy(currency_pair, Decimal(alt_amount))

            if suc:
                upbit_logger.info('BaseToAlt Alt구매 성공')
                break

            else:
                upbit_logger.info(msg)

                if '부족합니다.' in msg:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
        else:
            return False, '', '[Upbit]BaseToAlt실패 = [{}]'.format(msg)

        # 보내야하는 alt의 양 계산함.
        alt_amount *= ((1 - Decimal(td_fee)) ** 2)
        alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return True, alt_amount, '', 0

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        # currency_pair가 BTC_XRP 형식?
        currency_pair = currency_pair.split('_')[1]

        for _ in range(10):
            suc, data, msg, time_ = self.sell(currency_pair, alt_amount)

            if suc:
                upbit_logger.info('AltToBase ALT판매 성공')
                break

            else:
                upbit_logger.info(msg)

                if '부족합니다.' in msg:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue

        else:
            return False, '', '[Upbit]AltToBase실패 = [{}]'.format(msg)

        for _ in range(10):
            suc, data, msg, time_ = self.buy('BTC', btc_amount)

            if suc:
                upbit_logger.info('AltToBase Alt구매 성공')

                return True, '', '[Upbit]AltToBase ALT구매 성공', 0

            else:
                upbit_logger.info(msg)

                if '부족합니다.' in msg:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
        else:
            return False, '', '[Upbit]AltToBase실패 = [{}]'.format(msg)

        # 보내야하는 alt의 양 계산함.

    def get_step(self, price):
        if price >= 2000000:
            return 1000
        elif 2000000 > price >= 1000000:
            return 500
        elif 1000000 > price >= 500000:
            return 100
        elif 500000 > price >= 100000:
            return 50
        elif 100000 > price >= 10000:
            return 10
        elif 10000 > price >= 1000:
            return 5
        elif price < 10:
            return 0.01
        elif price < 100:
            return 0.1
        elif price < 1000:
            return 1

    def buy(self, coin, amount):
        upbit_logger.info('구매, Coin-[{}] Amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = 'KRW-{}'.format(coin.split('_')[1])

        tic_suc, price, tic_msg, tic_time = self.ticker(coin)

        if not tic_suc:
            return False, '', tic_msg, tic_time

        price = int(price)

        params = {
            'market': coin,
            'side': 'bid',
            'volume': str(amount),
            'price': (price * 1.05) + (self.get_step(price * 1.05) - ((price * 1.05) % self.get_step(price * 1.05))),
            'ord_type': 'limit'
        }

        suc, data, msg, times = self.private_api('POST', 'orders', params)

        return suc, data, msg, times

    def sell(self, coin, amount):
        upbit_logger.info('판매, Coin-[{}] Amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = 'KRW-{}'.format(coin.split('_')[1])

        tic_suc, price, tic_msg, tic_time = self.ticker(coin)

        if not tic_suc:
            return False, '', tic_msg, tic_time

        price = int(price)

        params = {
            'market': coin,
            'side': 'ask',
            'volume': str(amount),
            'price': (price * 0.95) - ((price * 0.95) % self.get_step(price * 0.95)),
            'ord_type': 'limit'
        }
        suc, data, msg, times = self.private_api('POST', 'orders', params)

        return suc, data, msg, times

    async def get_trading_fee(self):
        return True, 0.0005, '', 0


class UpbitUSDT(UpbitKRW):
    def __init__(self, key, secret):
        super().__init__(key, secret)

    def fee_count(self):
        return 2

    def buy(self, coin, amount):
        upbit_logger.info('구매, Coin-[{}] Amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = 'USDT-{}'.format(coin)

        tic_suc, price, tic_msg, tic_time = self.ticker(coin)

        if not tic_suc:
            return False, '', tic_msg, tic_time

        price = int(price)

        params = {
            'market': coin,
            'side': 'bid',
            'volume': str(amount),
            'price': (price * 1.05) + (self.get_step(price * 1.05) - ((price * 1.05) % self.get_step(price * 1.05))),
            'ord_type': 'limit'
        }

        suc, data, msg, times = self.private_api('POST', 'orders', params)

        return suc, data, msg, times

    def sell(self, coin, amount):
        upbit_logger.info('판매, Coin-[{}] Amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = 'USDT-{}'.format(coin)

        tic_suc, price, tic_msg, tic_time = self.ticker(coin)

        if not tic_suc:
            return False, '', tic_msg, tic_time

        price = int(price)

        params = {
            'market': coin,
            'side': 'ask',
            'volume': str(amount),
            'price': (price * 0.95) - ((price * 0.95) % self.get_step(price * 0.95)),
            'ord_type': 'limit'
        }
        suc, data, msg, times = self.private_api('POST', 'orders', params)

        return suc, data, msg, times


if __name__ == '__main__':
    upbit_key = 'xmH8ncO5PUZjV80VuWI68lxFuMDb4YRwxqh68XKW'
    upbit_secret = 'Ozxh418wnzqcOL5xz8SKn3cjEQqQ9K9K0SQPQbiG'

    id_ = 'rlah123@naver.com'
    pw_ = 'sj0227'
    u = UpbitKRW(upbit_key, upbit_secret)
    ub = UpbitBTC(upbit_key, upbit_secret)
    lo_suc, cookies_, lo_msg, lo_time = u.login(id_, pw_)
    u.decrypt_token(cookies_)

    # u.withdraw('BTC_BCC', 0.001, 'address')

    loop = asyncio.get_event_loop()
    check = loop.run_until_complete(u.compare_orderbook(ub, ['BTC_ETH', 'BTC_XRP']))

# CheckLikst
# Orderbook관련 - 이상 없음
# Balance - 이상 없음
# GetTransationFee - 이상 없음
# GetDepositAddrs - 이상 없음
# UPBIT-USDT 이상없음
# UPBIT-KRW, UPBIT-BTC 이상없음
# withdraw o