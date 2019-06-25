from pyinstaller_patch import *
from BaseExchange import *


class Huobi(BaseExchange):
    def __init__(self, key, secret):
        self._base_url = 'https://api.huobi.pro'
        self._key = key
        self._secret = secret

        self._sign_ver = 2
        self._sign_method = 'HmacSHA256'

        self._account_id = None

    def _get_account_id(self):
        for _ in range(10):
            success, data, message, time_ = self._private_api('GET', '/v1/account/accounts')

            if success:
                self._account_id = data['data'][0]['id']

                return True, self._account_id, '', 0
            else:
                time.sleep(time_)

        else:
            return False, '', '[Huobi]AccountID를 가져오는데 실패했습니다. [{}]'.format(message), time_

    def _get_transaction_list(self):
        return [
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

    def _get_header(self, method):
        if method == 'GET':
            return {"Content-type": "application/x-www-form-urlencoded",
                    'User-Agent': ('Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                   'Chrome/39.0.2171.71 Safari/537.36')}
        else:
            return {
                "Accept": "application/json",
                'Content-Type': 'application/json'
            }

    def _sign_generator(self, *args):
        method, path, params, sign_data = args

        if method == 'GET':
            params.update(sign_data)
            encode_qry = urlencode(sorted(params.items()))

        else:
            encode_qry = urlencode(sorted(sign_data.items()))

        payload = [method, 'api.huobi.pro', path, encode_qry]
        payload = '\n'.join(payload)

        sign = hmac.new(self._secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()

        return base64.b64encode(sign).decode()

    def _currencies(self):
        return self._public_api('GET', '/v1/common/currencys')

    def _private_api(self, method, path, extra=None):
        # previous name: api_request
        if extra is None:
            extra = {}

        sign_data = {
                    'AccessKeyId': self._key,
                    'SignatureMethod': 'HmacSHA256',
                    'SignatureVersion': self._sign_ver,
                    'Timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
                     }

        pointer = extra if method == 'GET' else sign_data

        pointer['Signature'] = self._sign_generator(method, path, extra, sign_data)

        if method == 'POST':
            path += '?' + urlencode(sign_data)

        return self._public_api(method, path, extra)

    def _public_api(self, method, path, extra=None, header=None):
        # previous name: http_request
        if extra is None:
            extra = {}

        try:
            header = self._get_header(method)
            path = self._base_url + path
            if method == 'GET':
                rq = requests.request(method, path, params=urlencode(extra), headers=header)

            else:
                rq = requests.request(method, path, data=json.dumps(extra), headers=header)

            rqj = rq.json()

            if rqj['status'] in 'error':
                return False, '', rqj['err-message'], 1
            else:
                return True, rqj, '', 0
        except Exception as ex:
            return False, '', '서버와 통신에 실패하였습니다 = [{}]'.format(ex), 1

    def get_precision(self):
        return True, (-8, -8), '', 0

    def fee_count(self):
        return 1

    def buy(self, coin, amount, price):
        coin = coin.split('_')
        currency_pair = coin[1].lower() + coin[0].lower()

        params = {
                    'account-id': str(self._account_id),
                    'symbol': currency_pair,
                    'amount': '{}'.format(amount).strip(),
                    'type': 'buy-market'
                  }

        return self._private_api('POST', '/v1/order/orders/place', params)

    def sell(self, coin, amount, price):

        coin = coin.split('_')
        currency_pair = coin[1].lower() + coin[0].lower()

        params = {
                    'account-id': str(self._account_id),
                    'symbol': currency_pair,
                    'amount': '{}'.format(amount).strip(),
                    'type': 'sell-market'
                  }

        return self._private_api('POST','/v1/order/orders/place', params)

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        success, data, message, time_ = self.buy(currency_pair, btc_amount)

        if success:
            coin = currency_pair.split('_')[1]  # 보내야하는 alt의 양 계산함.

            precision = alt_amount.as_tuple().exponent
            alt_amount *= (1 - Decimal(td_fee))
            alt_amount -= Decimal(tx_fee[coin])
            alt_amount = alt_amount.quantize(Decimal(10)**precision, rounding=ROUND_DOWN)

            return success, alt_amount, message, time_

        else:
            return success, data, '[Huobi]BaseToAlt 거래에 실패했습니다[{}]'.format(message), time_

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        coin = currency_pair[1]

        while True:
            success, data, message, time_ = self.sell(coin, alt_amount)

            if success:
                return success, data, message, time_

            else:
                time.sleep(time_)

    def withdraw(self, coin, amount, to_address, payment_id=None):
        params = {
                    'currency': coin.lower(),
                    'address': to_address,
                    'amount': '{}'.format(amount)
        }

        if payment_id:
            tag_dic = {'addr-tag': payment_id}
            params.update(tag_dic)

        return self._private_api('POST', '/v1/dw/withdraw/api/create', params)

    def get_available_coin(self):
        success, data, message, time_ = self._currencies()

        if not success:
            return False, '', '[Huobi]사용가능한 코인 값을 가져오지 못했습니다. [{}]'.format(message), 1

        else:
            # TODO 어떻게 리턴되는지 확인하고 작업하자
            pass

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

        _fee_info = {key: Decimal(_fee_info[key]).quantize(Decimal(10) ** -8) for key in _fee_info.keys()}

        return True, _fee_info, 'Success', 0

    async def _async_private_api(self, method, path, extra=None):
        sign_data = {
                    'AccessKeyId': self._key,
                    'SignatureMethod': self._sign_method,
                    'SignatureVersion': self._sign_ver,
                    'Timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
                     }

        pointer = extra if method == 'GET' else sign_data
        pointer['Signature'] = self._sign_generator(method, path, extra, sign_data)

        if method == 'POST':
            path += '?' + urlencode(sign_data)

        return self._async_public_api(method, path, extra)

    async def _async_public_api(self, method, path, extra=None, header=None):
        if extra is None:
            extra = {}

        try:
            async with aiohttp.ClientSession() as session:
                postdata = urlencode(extra) if method == 'GET' else json.dumps(extra)
                if method == 'GET':
                    rq = await session.get(path, params=postdata, headers=self._get_header(method))
                else:
                    rq = await session.post(path, data=postdata, headers=self._get_header(method))

                rq = await rq.text()
                rqj = json.loads(rq)

                if rqj['status'] in 'error':
                    return False, '', rqj['status'], 1
                else:
                    return True, rqj, '', 0

        except Exception as ex:
            return False, '', '서버와 통신에 실패하였습니다 = [{}]'.format(ex), 1

    async def get_deposit_addrs(self, coin_list=None):
        c_success, c_data, c_message, c_time_ = self._currencies()

        if c_success:
            try:
                coins = c_data['data']
                coin_addrs = {}

                for coin in coins:
                    success, data, _, _ = await self._async_private_api("GET", '/v1/query/deposit-withdraw',
                                                               {"currency": coin,  "type": "deposit",
                                                                "from": "0", "size": "100"
                                                                })
                    coin = coin.upper()
                    if success:
                        if data['data']:
                            coin_info = data['data'][0]
                            coin_addrs[coin] = coin_info['address']

                            if coin_info['currency'] in ['xrp', 'xmr', 'eos']:
                                coin_addrs[coin + 'TAG'] = coin_info['address-tag']

                return True, coin_addrs, '', 0
            except Exception as ex:
                return False, '', '[Huobi]주소를 가져오는데 실패했습니다. [{}]'.format(ex), 1
        else:
            return False, '', '[Huobi]사용가능한 코인을 가져오는데 실패했습니다. [{}]'.format(c_message), c_time_

    async def get_balance(self):
        if self._account_id is None:
            ac_success, _, ac_message, ac_time_ = self._get_account_id()

            if not ac_success:
                return False, '', ac_message, ac_time_

        success, data, message, time_ = await self._async_private_api(
                'GET', '/v1/account/accounts/{}/balance'.format(self._account_id), {'account-id': self._account_id})

        if success:
            balance = {}
            for info in data['data']['list']:
                if info['type'] == 'trade':

                    if float(info['balance']) > 0:
                        balance[info['currency'].upper()] = float(info['balance'])

            return True, balance, '', 0

        else:
            return False, '', '[Huobi]지갑 값을 가져오는데 실패했습니다. [{}]'.format(message), 5

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):  # 상위 평균매도/매수가 구함
        avg_order_book = {}
        for currency_pair in coin_list:
            if currency_pair == 'BTC_BTC':
                continue

            convert = currency_pair.split('_')
            coin = convert[1] + convert[0]

            avg_order_book[currency_pair] = {}

            success, data, m, t = await self._async_public_api('GET', self._base_url + '/market/depth',
                                                                 {'symbol': coin.lower(), 'type': 'step0'})

            if success:
                book = data['tick']
                for types in ['asks', 'bids']:
                    order_amount, order_sum = 0, 0

                    info = book[types]
                    for order_data in info:
                        order_amount += Decimal(order_data[1])
                        order_sum += (Decimal(order_data[0])
                                      * Decimal(order_data[1])).quantize(Decimal(10) ** -8)

                        if order_sum >= Decimal(btc_sum):
                            calc = ((order_sum / order_amount).quantize(Decimal(10) ** -8))
                            avg_order_book[currency_pair][types] = calc
                            break

            else:
                return False, '', '[Huobi]마켓의 과거 코인가격을 가져오는데 실패했습니다. [{}]'.format(m), t

        return True, avg_order_book, '', 0

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
        else:
            return False, '', 'huobi_error-[{}] other_error-[{}]'.format(huobi_msg, other_msg), huobi_times
