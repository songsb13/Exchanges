import json
import time
import base64
import hashlib
import hmac
import requests
from telegram import Bot
from telegram.error import TimedOut
import re
from decimal import Decimal, ROUND_DOWN
import asyncio
import aiohttp
import os
import sys
import logging

if 'pydevd' in sys.modules:
    coinone_logger = logging.getLogger(__name__)
    coinone_logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter('[%(asctime)s - %(lineno)d] %(message)s')

    file_handler = logging.FileHandler('Log.txt')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(fmt)

    coinone_logger.addHandler(file_handler)
    coinone_logger.addHandler(stream_handler)

    debugger = coinone_logger

else:
    coinone_logger = logging.getLogger('Debugger')


class OTPTimeOut(Exception):
    pass


class WrongOutputReceived(Exception):
    pass


class CoinOne:
    def __init__(self, __key, __secret, __token, __chat_id):
        self.apikey = __key
        self.secret = __secret
        self.otp = None
        self.token = __token
        self.chat_id = __chat_id

        self.message = None
        self.base_url = "https://api.coinone.co.kr"

    def fee_count(self):
        return 2

    def get_message(self):
        try:
            t = time.time()
            updates = self.bot.get_updates()
            if updates:
                update_id = updates[-1].update_id
            else:
                update_id = None
            while time.time() <= t + 170:
                try:
                    u = self.bot.get_updates()[-1]
                except TimedOut:
                    continue
                if u.update_id != update_id and str(u.message.chat_id) == str(self.chat_id):
                    txt = u.message.text
                    coinone_logger.info("{} 입력 받음".format(txt))
                    return txt
                time.sleep(1)
            return False
        except:
            coinone_logger.exception("텔레그램 에러발생")
            return False

    def public_call(self, endpoint, param={}):
        debugger.debug("CoinOne Public {} 호출시도".format(endpoint))
        try:
            if param:
                response = requests.get(self.base_url + endpoint, params=param)
            else:
                response = requests.get(self.base_url + endpoint)
        except Exception as e:
            debugger.debug("CoinOne Public API 호출실패!!")
            raise e
        try:
            result = response.json()
            debugger.debug("CoinOne Public API 호출 결과: {}".format(result))
            return result
        except Exception as e:
            debugger.debug("CoinOne Public API 결과값 이상: {}".format(response.text))
            raise e

    def private_call(self, endpoint, param={}):
        param['access_token'] = self.apikey
        param['nonce'] = int(time.time() * 1000)
        edata = base64.b64encode(json.dumps(param).encode())

        signature = hmac.new(self.secret.upper().encode(), edata, hashlib.sha512).hexdigest()
        header = {
            'Content-Type': 'application/json',
            'X-COINONE-PAYLOAD': edata,
            'X-COINONE-SIGNATURE': signature
        }

        try:
            debugger.debug("CoinOne Private {} 호출시도".format(endpoint))
            r = requests.post(self.base_url + endpoint, data=edata, headers=header)
        except Exception as e:
            debugger.debug("CoinOne Private API 호출실패!!")
            raise e

        try:
            result = r.json()
            debugger.debug("CoinOne Private API 호출 결과: {}".format(result))
            return result
        except Exception as e:
            debugger.debug("CoinOne Private API 결과값 이상: {}".format(r.text))
            raise e

    def ticker(self, currency='ALL'):
        try:
            result = self.public_call('/ticker/', param={'currency': currency})
            if result['errorCode'] != '0':
                return False, '', result['errorMsg'], 1
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 1

    def order_book(self, currency='btc'):
        try:
            result = self.public_call('/orderbook/', param={'currency': currency})
            if result['errorCode'] != '0':
                return False, '', result['errorMsg'], 3
            elif result['currency'].upper() != currency:
                return False, '', "Coinone[{}] 존재하지 않는 코인명 입니다.".format(currency), 0
            else:
                del result['timestamp']
                ret = {
                    'bids': result['bid'],
                    'asks': result['ask']
                }
                return True, ret, '', 0
        except Exception as e:
            return False, '', str(e), 3


    def sell_coin(self, coin, amount):
        success, ticker, err, st = self.ticker(coin)
        if not success:
            return False, '', err, st
        rate = int(float(ticker['high']) * 0.95)
        try:
            result = self.private_call('/v2/order/limit_sell/',
                                   {
                                       'price': rate,
                                       'qty': amount,
                                       'currency': coin
                                   })
            if result['errorCode'] != '0':
                return False, '', result['errorMsg'], 5
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 5

    # def sell_coin(self, coin, amount):
    #     r = self.public_call('/ticker/', param={'currency': coin})
    #
    #     rate = int(float(r.json()['high']) * 0.95)
    #
    #     result = self.private_call('/v2/order/limit_sell/',
    #                                {
    #                                    'price': rate,
    #                                    'qty': amount,
    #                                    'currency': coin
    #                                })
    #     if not result:
    #         raise WrongOutputReceived("CoinOne Sell 예외발생")
    #     elif result['errorCode'] != '0':
    #         coinone_logger.info("CoinOne Sell 예외발생")
    #         return False
    #     else:
    #         return result
    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        alt = Decimal(alt_amount)
        success, result, error, ts = self.sell_coin('BTC', btc_amount)
        if not success:
            coinone_logger.info(error)
            return False, '', error, ts
        while True:
            success, result, error, ts = self.buy_coin(currency_pair.split('_')[1], alt_amount)
            if success:
                break
            coinone_logger.info(error)
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

        return True, alt, '', 0

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        while True:
            success, result, error, ts = self.sell_coin(currency_pair.split('_')[1], alt_amount)
            if success:
                break
            coinone_logger.info(error)
            time.sleep(ts)
        while True:
            success, result, error, ts = self.buy_coin('BTC', btc_amount)
            if success:
                break
            coinone_logger.info(error)
            time.sleep(ts)

    def buy_coin(self, coin, amount):
        success, ticker, err, st = self.ticker(coin)
        if not success:
            return False, '', err, st
        rate = int(float(ticker['low']) * 1.05)

        try:
            result = self.private_call('https://api.coinone.co.kr/v2/order/limit_buy/',
                                       {
                                           'price': rate,
                                           'qry': amount,
                                           'currency': coin
                                       })
            if result['errorCode'] != '0':
                return False, '', result['errorMsg'], 5
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 5


    # def buy_coin(self, coin, amount):
    #     r = self.public_call('/ticker/', param={'currency': coin})
    #
    #     rate = int(float(r.json()['low']) * 1.05)
    #
    #     result = self.private_call('https://api.coinone.co.kr/v2/order/limit_buy/',
    #                                {
    #                                    'price': rate,
    #                                    'qry': amount,
    #                                    'currency': coin
    #                                })
    #
    #     if not result:
    #         raise WrongOutputReceived("CoinOne Buy 예외발생")
    #     elif result['errorCode'] != '0':
    #         coinone_logger.info("CoinOne Buy 예외발생")
    #         return False
    #     else:
    #         return result

    def auth2factor(self, currency):
        params = {
            'type': currency
        }
        #   해당 currency의 송금확인 인증번호가 핸드폰으로 발송된다..
        try:
            result = self.private_call('/v2/transaction/auth_number/', params)
            if result['errorCode'] != '0':
                return False, '', result['errorMsg'], 5
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def withdraw(self, coin, amount, to_address, payment_id=None):
        success, msg, err, ts = self.auth2factor(coin)
        if success:
            try:
                self.bot.sendMessage(self.chat_id, 'OTP 패스워드를 입력해주세요')
            except Exception as e:
                return False, '', str(e), 5
        else:
            coinone_logger.info(err)
            return False, '', err, 5
        code = self.get_message()
        if not code:
            self.bot.send_message(self.chat_id, '인증번호 입력시간을 초과했습니다.')
            coinone_logger.info("인증번호 입력시간을 초과했습니다.")
            os.system("PAUSE")
            return False, '', "인증번호 입력시간을 초과했습니다.", 5
        params = {
            'currency': coin,
            'address': to_address,
            'auth_number': code,
            'qty': amount
        }
        if payment_id is not None:
            params.update({'paymentId': payment_id})

        try:
            result = self.private_call('/v2/transaction/coin/', params)
            if result['errorCode'] != '0':
                return False, '', result['errorMsg'], 5
            else:
                return True, result, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def get_available_coin(self):
        loop = asyncio.new_event_loop()
        while True:
            success, fee, err, st = loop.run_until_complete(self.get_transaction_fee)
            if not success:
                time.sleep(st)
                continue
            ret = []
            for k in fee.keys():
                if k == 'BTC':
                    continue
                ret.append('BTC_' + k)
            break
        loop.close()
        return ret

    async def balance(self):
        try:
            result = self.private_call('/v2/account/balance/')
            if result['errorCode'] != '0':
                return False, '', result['errorMsg'], 5
            else:
                ret = {}
                for key in result:
                    if key == 'errorCode' or key == 'result' or key == 'normalWallets':
                        continue
                    ret[key.upper()] = float(result[key]['balance'])
                return True, ret, '', 0
        except Exception as e:
            return False, '', str(e), 5

    async def get_trading_fee(self):
        try:
            result = self.private_call('/v2/account/user_info/')
            if result['errorCode'] != '0':
                return False, '', result['errorMsg'], 5
            else:
                fee = result['userInfo']['feeRate']
                return True, float(fee['btc']['taker']), '', 0
        except Exception as e:
            return False, '', str(e), 5

    async def get_transaction_fee(self):
        return True, {
            'BTC': Decimal(0.0015).quantize(Decimal(10) ** -8),
            'BCH': Decimal(0.0005).quantize(Decimal(10) ** -8),
            'ETH': Decimal(0.01).quantize(Decimal(10) ** -8),
            'ETC': Decimal(0.01).quantize(Decimal(10) ** -8),
            'XRP': Decimal(1).quantize(Decimal(10) ** -8),
            'QTUM': Decimal(0.01).quantize(Decimal(10) ** -8),
            'LTC': Decimal(0.005).quantize(Decimal(10) ** -8),
            'IOTA': Decimal(0).quantize(Decimal(10) ** -8),
            'BTG': Decimal(0.0005).quantize(Decimal(10) ** -8),
            'OMG': Decimal(.15).quantize(Decimal(10) ** -8),
            'EOS': Decimal(0).quantize(Decimal(10) ** -8),
            'DATA': Decimal(25).quantize(Decimal(10) ** -8),
            'ZIL': Decimal(20).quantize(Decimal(10) ** -8),
            'KNC': Decimal(2).quantize(Decimal(10) ** -8),
            'ZRX': Decimal(2).quantize(Decimal(10) ** -8),
        }, '', 0

    async def get_deposit_addrs(self):
        ret_data = {}
        err = ""
        for _ in range(5):
            res = self.private_call('/v2/account/deposit_address/')
            if res['errorCode'] == '0':
                break
            else:
                debugger.info("[Coinone 입금 주소 조회 실패] {}".format(res))
                err = res['errorMsg']
                await asyncio.sleep(10)
        else:
            return False, '', err, 10

        addrs = res['walletAddress']

        for c in addrs.keys():
            if not addrs[c] or addrs[c] == '-1':
                #   xrp_tag 는 없을 경우 -1이나옴
                continue
            if c == 'eos_memo':
                c = 'eos_tag'
            ret_data[c.upper().replace('_', '')] = addrs[c]

        return True, ret_data, '', 0

    async def get_curr_avg_orderbook(self, currencies, default_btc=1):
        ret = {}
        btc_avg = {}
        for order_type in ['bids', 'asks']:
            success, orderbook, err, st = self.order_book('BTC')
            if not success:
                return False, '', err, st
            rows = orderbook[order_type]
            total_price = Decimal(0.0)
            total_amount = Decimal(0.0)
            for row in rows:
                total_price += Decimal(row['price']) * Decimal(row['qty'])
                total_amount += Decimal(row['qty'])
                if total_amount >= default_btc:
                    break
            btc_avg[order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)

        for c in currencies:
            ret[c] = {}
            alt = c.split('_')[1]
            for order_type in ['bids', 'asks']:
                success, orderbook, err, st = self.order_book(alt)
                if not success:
                    return False, '', err, st
                rows = orderbook[order_type]
                total_price = Decimal(0.0)
                total_amount = Decimal(0.0)
                for row in rows:
                    if order_type == 'bids':
                        total_price += Decimal(row['price']) / btc_avg['asks'] * Decimal(row['qty'])
                    else:
                        total_price += Decimal(row['price']) / btc_avg['bids'] * Decimal(row['qty'])
                    total_amount += Decimal(row['qty'])

                    if total_price >= default_btc:
                        break
                ret[c][order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)

        return True, ret, '', 0

    async def compare_orderbook(self, other, coins=[], default_btc=1):
        # currency_pairs = ['BTC_' + coin for coin in coins if coin != 'BTC']
        currency_pairs = coins
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            coinone_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs, default_btc),
                                                                other.get_curr_avg_orderbook(currency_pairs, default_btc))
            success, coinone_avg_orderbook, err, st = coinone_result
            success2, other_avg_orderbook, err2, st2 = other_result
            if success and success2:
                m_to_s = {}
                for currency_pair in currency_pairs:
                    m_ask = coinone_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in currency_pairs:
                    m_bid = coinone_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))
                ret = (coinone_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m})
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
