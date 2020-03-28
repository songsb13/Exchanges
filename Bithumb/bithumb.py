import re
import hmac
import base64
import time
import requests
import hashlib
import json
import aiohttp
import asyncio

from lxml import html as lh
from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlencode

from base_exchange import BaseExchange, ExchangeResult


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


class BaseBithumb(BaseExchange):
    def __init__(self, key, secret):
        self._key = key
        self._secret = secret
        self._base_url = 'https://api.bithumb.com'

        ExchangeResult.set_exchange_name = 'Bithumb'

    def _sign_generator(self, *args):
        extra, data, path, nonce = args
        hmac_data = path + chr(0) + data + chr(0) + nonce
        hashed = hmac.new(self._secret.encode('utf-8'), hmac_data.encode('utf-8'), hashlib.sha512).hexdigest()

        signature = base64.b64encode(hashed.encode('utf-8')).decode('utf-8')

        return signature

    def _public_api(self, method, path, extra=None, header=None):
        debugger.debug('[Bithumb]Parameters=[{}, {}, {}, {}], function name=[_public_api]'.format(method, path, extra, header))

        try:
            extra = dict() if extra is None else urlencode(extra)

            rq = requests.get(self._base_url + path, data=extra)

            response = rq.json()

            error_message = None if response['status'] == '0000' else 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.\
                format(response['message'], path, extra)

        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)
        return ExchangeResult(*result)

    def _private_api(self, method, path, extra=None):
        debugger.debug('[Bithumb]Parameters=[{}, {}, {}], function name=[_private_api]'.format(method, path, extra))

        try:
            extra = dict() if extra is None else extra

            extra.update({'endpoint': path})

            nonce = str(int(time.time() * 1000))
            data = urlencode(extra)
            signature = self._sign_generator(extra, data, path, nonce)

            headers = {
                'Content-Type': settings.CONTENT_TYPE,
                'Api-Key': self._key,
                'Api-Sign': signature,
                'Api-Nonce': nonce
            }

            rq = requests.post(self._base_url + path, headers=headers, data=extra)

            response = rq.json()

            error_message = None if response['status'] == '0000' else 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'. \
                format(response['message'], path, extra)

        except Exception as ex:
            error_message = 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)
        return ExchangeResult(*result)

    def fee_count(self):
        return 2

    def get_ticker(self, market):
        for _ in range(3):
            result_object = self._public_api('GET', '/public/ticker/{}'.format(market))
            if result_object:
                break

            time.sleep(result_object.wait_time)

        return result_object

    def limit_buy(self, coin, amount, price):
        params = {
            'order_currency': coin,
            'payment_currency': 'KRW',
            'units': amount,
            'price': price,
            'type': 'bid'
        }

        return self._private_api('POST', '/trade/place', params)

    def limit_sell(self, coin, amount, price):
        params = {
            'order_currency': coin,
            'payment_currency': 'KRW',
            'units': amount,
            'price': price,
            'type': 'ask'
        }

        return self._private_api('POST', '/trade/place', params)

    def buy(self, coin, amount, price=None):
        debugger.debug('[Bithumb]Parameters=[{}, {}, {}], function name=[buy]'.format(coin, amount, price))

        params = {
            'currency': coin,
            'units': amount
        }

        if price:
            return self.limit_buy(coin, amount, price)

        return self._private_api('POST', '/trade/market_buy', params)

    def sell(self, coin, amount, price=None):
        debugger.debug('[Bithumb]Parameters=[{}, {}, {}], function name=[sell]'.format(coin, amount, price))

        params = {
            'currency': coin,
            'units': amount
        }

        if price:
            return self.limit_sell(coin, amount, price)

        return self._private_api('POST', '/trade/market_sell', params)

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        alt = Decimal(alt_amount).quantize(Decimal(10) ** -8)
        for _ in range(10):
            sell_result_object = self.sell('BTC', btc_amount)
            if sell_result_object.success:
                break
            time.sleep(sell_result_object.wait_time)

        else:
            return sell_result_object

        currency_pair = currency_pair.split('_')[1]
        for _ in range(10):
            buy_result_object = self.buy(currency_pair, alt_amount)
            if buy_result_object.success:
                break

            time.sleep(buy_result_object.wait_time)
        else:
            return buy_result_object

        alt *= ((1 - Decimal(td_fee)) ** 2)
        alt -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt = alt.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        result = (True, alt)

        return ExchangeResult(*result)

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        currency_pair = currency_pair.split('_')[1]
        for _ in range(10):
            sell_result_object = self.sell(currency_pair, alt_amount)
            if sell_result_object.success:
                break
            time.sleep(sell_result_object.wait_time)
        else:
            return sell_result_object

        for _ in range(10):
            buy_result_object = self.buy('BTC', btc_amount)
            if buy_result_object.success:
                break

            time.sleep(buy_result_object.wait_time)
        else:
            return buy_result_object

        result = (True, )

        return ExchangeResult(*result)

    def withdraw(self, coin, amount, to_address, payment_id=None):
        debugger.debug('[Bithumb]Parameters=[{}, {}, {}], function name=[withdraw]'.format(coin, amount, to_address, payment_id))

        params = {
            'currency': coin,
            'units': amount,
            'address': to_address
        }
        if payment_id:
            params.update({'destination': payment_id})

        return self._private_api('POST', '/trade/btc_withdrawal', params)

    def get_available_coin(self):
        available_coin = [
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

        result = (True, available_coin)

        return ExchangeResult(*result)

    def get_precision(self, pair=None):
        return ExchangeResult(True, (-8, -8))

    async def _async_private_api(self, method, path, extra=None):
        debugger.debug('[Bithumb]Parameters=[{}, {}, {}], function name=[_async_private_api]'.format(method, path, extra))
        try:
            extra = dict() if extra is None else extra

            nonce = str(int(time.time() * 1000))
            data = urlencode(extra)
            signature = self._sign_generator(extra, data, path, nonce)
            header = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Api-Key': self._key,
                'Api-Sign': signature,
                'Api-Nonce': nonce
            }

            async with aiohttp.ClientSession(headers=header) as session:
                rq = await session.post(self._base_url + path, data=data)

                response = json.loads(await rq.text())

                error_message = None if response['status'] == '0000' else 'ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.\
                    format(response['message'], path, extra)

        except Exception as ex:
            error_message = ' ERROR_BODY=[{}], URL=[{}], PARAMETER=[{}]'.format(ex, path, extra)

        result = (True, response, '', 0) if error_message is None else (False, '', error_message, 1)

        return ExchangeResult

    async def _get_deposit_addrs(self, currency):
        for _ in range(3):
            result_object = await self._async_private_api('POST', '/info/wallet_address',
                                                                          {'currency': currency})

            if result_object.success:
                break
            time.sleep(result_object.wait_time)

        return result_object

    async def _get_orderbook(self, symbol):
        for _ in range(3):
            result_object = self._public_api('GET', '/public/orderbook/{}'.format(symbol))
            if result_object.success:
                break

            time.sleep(result_object.wait_time)

        return result_object

    async def _get_balance(self):
        for _ in range(3):
            result_object = await self._async_private_api('POST', '/info/balance', {'currency': 'ALL'})
            if result_object.success:
                break

            time.sleep(result_object.wait_time)

        return result_object

    async def _get_trading_fee(self, symbol):
        for _ in range(3):
            result_object = await self._async_private_api('POST', '/info/account', {'currency': symbol})
            if result_object.success:
                break

            time.sleep(result_object.wait_time)

        return result_object

    async def get_balance(self):
        result_object = await self._get_balance()

        if result_object.success:
            data = result_object.data
            response = {key.split('_')[1].upper(): float(data['data'][key]) for key in data['data'] if
                        key.startswith('available') and float(data['data'][key]) > 0}

            result_object.data = response

        return result_object

    async def get_trading_fee(self):
        result_object = await self._get_trading_fee('BTC')
        if result_object.success:
            result_object.data = result_object.data['data']['trade_fee']

        return result_object

    async def get_transaction_fee(self):
        # 현철이 레거시
        try:
            ret = requests.get('https://www.bithumb.com/u1/US138', timeout=60)
            #   API 사용이 아니다.
            doc = lh.fromstring(ret.text)
            tags = doc.cssselect('table.g_tb_normal.fee_in_out tr')

            ret_data = dict()
            for tag in tags[3:]:
                key = re.search('[A-Z]+', tag.cssselect('td.money_type')[0].text_content()).group()
                try:
                    val = tag.cssselect('div.right')[1].text_content()
                except IndexError:
                    continue
                try:
                    ret_data[key] = Decimal(val).quantize(Decimal(10) ** -8)
                except ValueError:
                    pass

            self.transaction_fee = ret_data if ret_data else self.transaction_fee

            result = (False, '', 'ERROR_BODY=[트랜젝션 수수료 없음 에러]', 5) if ret_data is dict() \
                else (True, ret_data, '', 0)

        except Exception as ex:
            result = (False, '', 'ERROR_BODY=[{}]'.format(ex), 5) if self.transaction_fee is None \
                else (True, self.transaction_fee, '', 0)

        return ExchangeResult(*result)

    async def get_deposit_addrs(self, coin_list=None):
        ret_data = dict()
        failed_log = str()
        # bithumb의 get_available_coin은 하드코딩이므로 data외 값을 받을 필요 없음.
        available_result_object = self.get_available_coin()
        available_coin = available_result_object.data + ['BTC_BTC']
        for currency in available_coin:
            # todo test시 결과 값 보고 수정처리 필요.
            currency = currency[4:]

            deposit_result_object = await self._get_deposit_addrs(currency)
            if deposit_result_object.success:
                data = deposit_result_object.data
                if currency in settings.SUB_ADDRESS_COIN_LIST:
                    try:
                        address, tag = data['data']['wallet_address'].split('&dt=')
                        ret_data[currency + 'TAG'] = tag
                        ret_data[currency] = address
                    except ValueError:
                        ret_data[currency] = str()
                        ret_data[currency + 'TAG'] = str()
                else:
                    ret_data[currency] = data['data']['wallet_address']

            else:
                failed_log += deposit_result_object.message + '\n'

        result = (True, ret_data, failed_log, 0)

        return ExchangeResult(*result)

    async def get_curr_avg_orderbook(self, currencies, default_btc=1):
        ret = dict()
        success, data, message, time_ = await self._get_orderbook('ALL')
        if not success:
            return False, '', message, time_

        btc_avg = dict()
        data = data['data']
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

    async def compare_orderbook(self, other, coins, default_btc=1):
        currency_pairs = coins
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            bithumb_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs,
                                                                                             default_btc),
                                                                 other.get_curr_avg_orderbook(currency_pairs,
                                                                                              default_btc))
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
    k = ''
    s = ''

    b = BaseBithumb(key=k, secret=s)
    loop = asyncio.get_event_loop()
    _, available, *_ = b.get_available_coin()
    s, d, m, t = loop.run_until_complete(b.get_curr_avg_orderbook(available))
    print(d)

    # s, d, m, t = b.get_available_coin()
    # s, d, m, t = b.buy('ETH', 1)
    # s, d, m, t = b.sell('ETH', 1)
    # s, d, m, t = b.limit_buy('ETH', 1, 100)
    # s, d, m, t = b.limit_sell('ETH', 1, 100)
    # s, d, m, t = b.withdraw('ETH', 1, 'test')
    # s, d, m, t = loop.run_until_complete(b.get_balance())
    # s, d, m, t = loop.run_until_complete(b.get_trading_fee())
    # s, d, m, t = loop.run_until_complete(b.get_transaction_fee())
    # s, d, m, t = loop.run_until_complete(b.get_deposit_addrs())
    # s, d, m, t = loop.run_until_complete(b.get_curr_avg_orderbook(available))
