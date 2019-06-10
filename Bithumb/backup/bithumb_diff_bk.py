import asyncio
import requests
from urllib.parse import urlencode
import base64
import logging
import sys
import os
import hmac
import hashlib
import time
from decimal import Decimal, ROUND_DOWN
from lxml import html as lh
import re

if 'pydevd' in sys.modules:
    bithumb_logger = logging.getLogger(__name__)
    bithumb_logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter('[%(asctime)s - %(lineno)d] %(message)s')

    file_handler = logging.FileHandler('Log.txt')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(fmt)

    bithumb_logger.addHandler(file_handler)
    bithumb_logger.addHandler(stream_handler)

    debugger = bithumb_logger

else:
    bithumb_logger = logging.getLogger('Debugger')


class WrongOutputReceived(Exception):
    pass


class RequestError(Exception):
    def __init__(self, status):
        self.code = int(status)

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

        return "[{code}] 다음과 같은 에러가 발생하였습니다: {err_content}".format(
            code=self.code, err_content=codelist[self.code]
        )


class Bithumb:
    def __init__(self, api_key, secret):
        self.api_key = api_key
        self.secret = secret
        self.base_url = "https://api.bithumb.com"
        self.transaction_fee = None

    def fee_count(self):
        return 2

    def public_call(self, endpoint, extra_params={}):
        debugger.debug("Bithumb Public {} 호출시도".format(endpoint))
        try:
            if extra_params:
                data = urlencode(extra_params)
                response = requests.get(self.base_url + endpoint, data=data)
            else:
                response = requests.get(self.base_url + endpoint)
        except Exception as e:
            debugger.debug("Bithumb Public API 호출실패!!")
            raise e
        try:
            result = response.json()
            debugger.debug("Bithumb Public API 호출 결과: {}".format(result))
            return result
        except Exception as e:
            debugger.debug("Bithumb Public API 결과값 이상: {}".format(response.text))
            raise e

    def private_call(self, endpoint, extra_params={}):
        extra_params.update({'endpoint': endpoint})

        nonce = str(int(time.time() * 1000))
        data = urlencode(extra_params)
        hmac_data = endpoint + chr(0) + data + chr(0) + nonce
        hashed = hmac.new(self.secret.encode('utf-8'), hmac_data.encode('utf-8'), hashlib.sha512).hexdigest()
        signature = base64.b64encode(hashed.encode('utf-8')).decode('utf-8')

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Api-Key': self.api_key,
            'Api-Sign': signature,
            'Api-Nonce': nonce
        }

        try:
            debugger.debug("Bithumb Private {} 호출시도".format(endpoint))
            response = requests.post(self.base_url + endpoint, headers=headers, data=data)
        except Exception as e:
            debugger.debug("Bithumb Private API 호출실패!!")
            raise e

        try:
            result = response.json()
            debugger.debug("Bithumb Private API 호출 결과: {}".format(result))
            return result
        except Exception as e:
            debugger.debug("Bithumb Private API 결과값 이상: {}".format(response.text))
            raise e

    def order_book(self):
        try:
            result = self.public_call('/public/orderbook/ALL')
            if result['status'] != '0000':
                return False, '', result['message'], 1
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 1

    def ticker(self, currency='ALL'):
        try:
            result = self.public_call('/public/ticker/' + currency)
            if result['status'] != '0000':
                return False, '', result['message'], 1
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 1
    # def order_book(self):
    #     ob = self.public_call('/public/orderbook/ALL')
    #     for _ in range(60):
    #         ob = self.public_call('/public/orderbook/ALL')
    #         if not ob:
    #             bithumb_logger.info("오더북 조회 실패")
    #         elif ob['status'] != '0000':
    #             #   결과는 나왔으나 에러코드가 발생한 경우
    #             bithumb_logger.info("에러 발생")
    #         else:
    #             result = ob['data']
    #             del result['payment_currency']
    #             del result['timestamp']
    #
    #             return result

    # def ticker(self, currency='ALL'):
    #     result = self.public_call('/public/ticker/' + currency)
    #
    #     if not result:
    #         #   에러가 발생하여 None 이 Return 된 경우
    #         #   네트워크 에러 혹은 리턴결과가 json 형식이 아닐 경우에만 발생
    #         raise WrongOutputReceived("Bithumb Sell 예외발생")
    #     elif result['status'] != '0000':
    #         #   결과는 나왔으나 에러코드가 발생한 경우
    #         raise RequestError(result['status'])
    #     else:
    #         #   혹시나 결과값을 이용할 일이 생길 때를 대비함
    #         return result

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        alt = Decimal(alt_amount)
        success, result, error, ts = self.sell_coin('BTC', btc_amount)
        if not success:
            bithumb_logger.info(error)
            time.sleep(ts)
            return False
        while True:
            success, result, error, ts = self.buy_coin(currency_pair.split('_')[1], alt_amount)
            if success:
                break
            bithumb_logger.info(error)
            time.sleep(ts)
        # loop = asyncio.get_event_loop()
        # while True:
        #     td, tx = loop.run_until_complete(
        #         asyncio.gather(self.get_trading_fee(), self.get_transaction_fee())
        #     )
        #     if td[0] and tx[0]:
        #         break
        # loop.close()
        #
        # td_fee = td[1]
        # tx_fee = tx[1]
        alt *= ((1 - Decimal(td_fee)) ** 2)
        alt -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt = alt.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return alt

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        while True:
            success, result, error, ts = self.sell_coin(currency_pair.split('_')[1], alt_amount)
            if success:
                break
            bithumb_logger.info(error)
            time.sleep(ts)
        while True:
            success, result, error, ts = self.buy_coin('BTC', btc_amount)
            if success:
                break
            bithumb_logger.info(error)
            time.sleep(ts)

    def sell_coin(self, coin, amount):
        params = {'currency': coin, 'units': amount}
        try:
            result = self.private_call('/trade/market_sell', extra_params=params)
            if result['status'] != '0000':
                return False, '', result['message'], 5
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 1

    def buy_coin(self, coin, amount):
        params = {'currency': coin, 'units': amount}
        try:
            result = self.private_call('/trade/market_buy', extra_params=params)
            if result['status'] != '0000':
                return False, '', result['message'], 5
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 1

    def withdraw(self, coin, amount, to_address, payment_id=None):
        params = {
            'currency': coin,
            'units': amount,
            'address': to_address
        }
        if coin == 'XMR' or coin == 'XRP':
            params.update({'destination': payment_id})

        try:
            res = self.private_call('/trade/btc_withdrawal', params)
            if res['status'] != '0000':
                return False, '', res['message'], 5
            else:
                return True, res, '', 0
        except Exception as e:
            return False, '', str(e), 5

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

    async def balance(self):
        params = {'currency': 'ALL'}
        try:
            res = self.private_call('/info/balance', extra_params=params)
            if res['status'] != '0000':
                return False, '', res['message'], 1

            ret_data = {key.split('_')[1].upper(): float(res['data'][key]) for key in res['data'] if
                        key.startswith('available') and float(res['data'][key]) > 0}
            return True, ret_data, '', 0
        except Exception as e:
            return False, '', str(e), 1

    async def get_trading_fee(self):
        params = {'currency': 'BTC'}
        try:
            res = self.private_call('/info/account', extra_params=params)
            if res['status'] != '0000':
                return False, '', res['message'], 5
            ret_data = res['data']['trade_fee']
            return True, float(ret_data), '', 0
        except Exception as e:
            return False, '', str(e), 5

    async def get_transaction_fee(self):
        try:
            ret = requests.get('https://www.bithumb.com/u1/US138', timeout=60)
        except:
            if self.transaction_fee is not None:
                return True, self.transaction_fee, '', 0
            else:
                return False, '', "트랜잭션 수수료 불러오기 에러", 5

        #   API 사용이 아니다.
        doc = lh.fromstring(ret.text)
        tags = doc.cssselect('table.g_table_list.fee_in_out tr')

        ret_data = {}
        for tag in tags[3:]:
            key = re.search('[A-Z]+', tag.cssselect('td.money_type')[0].text_content()).group()
            try:
                val = tag.cssselect('div.right')[1].text_content()
            except IndexError:
                continue
            try:
                ret_data[key] = float(val)
            except ValueError:
                bithumb_logger.info("예외발생; KEY: {}\tVAL: {}".format(key, val))

        self.transaction_fee = ret_data

        return True, self.transaction_fee, '', 0

    async def get_deposit_addrs(self):
        ret_data = {}
        err = ""
        for currency in self.get_available_coin() + ['BTC_BTC']:
            currency = currency[4:]
            for _ in range(5):
                res = self.private_call('/info/wallet_address', extra_params={'currency': currency})
                if res['status'] == '0000':
                    break
                else:
                    debugger.info('[Bithumb 입금 주소 조회 실패] {}'.format(res))
                    err = res['message']
                    await asyncio.sleep(10)
            else:
                return False, '', err, 10

            if currency == 'XRP':
                try:
                    address, tag = res['data']['wallet_address'].split('&dt=')
                    ret_data['XRPTAG'] = tag
                    ret_data[currency] = address
                except ValueError:
                    ret_data[currency] = ''
                    ret_data['XRPTAG'] = ''
            else:
                ret_data[currency] = res['data']['wallet_address']

        return True, ret_data, '', 0

    async def get_curr_avg_orderbook(self, currencies, default_btc=1):
        ret = {}
        err = "오더북 조회 에러"
        st = 5
        #   만약 err과 st가 설정아 안된 경우
        for _ in range(3):
            success, data, err, st = self.order_book()
            if success:
                break
            await asyncio.sleep(st)
        else:
            return False, '', err, st
        btc_avg = {}
        for order_type in ['bids', 'asks']:
            rows = data['BTC'][order_type]
            total_price = Decimal(0.0)
            total_amount = Decimal(0.0)
            for row in rows:
                total_price += Decimal(row['price']) * Decimal(row['quantity'])
                total_amount += Decimal(row['quantity'])

                if total_amount >= default_btc:
                    break

            btc_avg[order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)

        del data['BTC']

        for c in data:
            if 'BTC_' + c.upper() not in currencies:
                #   parameter 로 들어온 페어가 아닌 경우에는 제외
                continue
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

                    if total_price >= default_btc:
                        break

                ret['BTC_'+c.upper()][order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)
        return True, ret, '', 0

    async def compare_orderbook(self, other, coins=[], default_btc=1):
        currency_pairs = ['BTC_' + coin for coin in coins if coin != 'BTC']
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            bithumb_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs, default_btc),
                                                                other.get_curr_avg_orderbook(currency_pairs, default_btc))
            # success, bithumb_avg_orderbook, err, st = await self.get_curr_avg_orderbook(currency_pairs, default_btc)
            # other_avg_orderbook = await other.get_curr_avg_orderbook(currency_pairs, default_btc)
            success, bithumb_avg_orderbook, err, st = bithumb_result
            success2, other_avg_orderbook, err2, st2 = other_result
            if success and success2:
                m_to_s = {}
                for currency_pair in currency_pairs:
                    m_ask = bithumb_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in currency_pairs:
                    m_bid = bithumb_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                ret = (bithumb_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m})

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


if __name__ == '__main__':
    bit = Bithumb('5921ef4e1e53622c4d46f827e3fcb527', '687d509dbaeaa2a01675bed46e629551')
    loop = asyncio.get_event_loop()
    data = loop.run_until_complete(bit.get_deposit_addrs())
    loop.close()
    print(data)
