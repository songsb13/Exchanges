from BaseExchange import *


class BaseUpbit(BaseExchange):
    def __init__(self, key, secret):
        self._base_url = 'https://api.upbit.com/v1'
        self._key = key
        self._secret = secret

    def __repr__(self):
        return 'BaseUpbit'

    def _public_api(self, method, path, extra=None, header=None):
        if header is None:
            header = {}

        if extra is None:
            extra = {}

        method = method.upper()
        path = '/'.join([self._base_url, path])
        if method == 'GET':
            rq = requests.get(path, headers=header, json=extra)
        elif method == 'POST':
            rq = requests.post(path, headers=header, params=extra)
        else:
            return False, '', '[{}]incorrect method'.format(method), 1

        try:
            res = rq.json()

            if 'error' in res:
                return False, '', res['error']['message'], 1

            else:
                return True, res, '', 0

        except Exception as ex:
            return False, '', 'Error [{}]'.format(ex), 1

    def _private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }

        if extra is not None:
            payload.update({'query': urlencode(extra)})

        header = self._sign_generator(payload)

        return self._public_api(method, path, extra, header)

    def _sign_generator(self, *args):
        payload = args
        return 'Bearer {}'.format(jwt.encode(payload, self._secret,).decode('utf8'))

    def fee_count(self):
        # 몇변의 수수료가 산정되는지
        return 1

    def get_ticker(self, market):
        for _ in range(3):
            success, data, message, time_ = self._public_api('get', 'ticker', market)

            if success:
                return True, data, message, time_
            time.sleep(time_)

        else:
            return False, '', message, time_

    def _currencies(self):
        # using get_currencies, service_currencies
        for _ in range(3):
            success, data, message, time_ = self._public_api('get', '/'.join(['market', 'all']))

            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    def get_available_coin(self):
        success, currencies, message, time_ = self._currencies()

        if not success:
            return False, '', '[Upbit]사용 가능코인을 가져오는데 실패했습니다.', time_

        else:
            # todo 전체 코인 값이 들어오나? 그러면 BTC만 가져오게?
            res = []
            [res.append(data.replace('-', '_')) for data in currencies if currencies['market'].split('-')[1] not in res]
            return True, res, '', 0

    def service_currencies(self, currencies):
        # using deposit_addrs
        res = []
        return [res.append(data.split('-')[1]) for data in currencies if currencies['market'].split('-')[1] not in res]

    def get_order_history(self, uuid):
        return self._private_api('get', 'order', {'uuid': uuid})

    def withdraw(self, coin, amount, to_address, payment_id=None):
        params = {
                    'currency': coin,
                    'address': to_address,
                    'amount': str(amount),
                }

        if payment_id:
            params.update({'secondary_address': payment_id})

        return self._private_api('post', '/'.join(['withdraws', 'coin']), params)

    def buy(self, coin, amount, price=None):
        if price is None:
            success, data, message, time_ = self.get_ticker(coin)
            if not success:
                return False, '', message, time_

            price = data['price']  # todo 확인 해볼것.

        amount, price = map(str, (amount, price * 1.05))
        coin = coin.split('_')[1]

        params = {
            'market': coin,
            'side': 'bid',
            'volume': amount,
            'price': price,
            'ord_type': 'limit'
        }

        return self._private_api('POST', 'orders', params)

    def sell(self, coin, amount, price=None):
        if price is None:
            success, data, message, time_ = self.get_ticker(coin)
            if not success:
                return False, '', message, time_

            price = data['price']  # todo 확인 해볼것.

        amount, price = map(str, (amount, price * 0.95))
        coin = coin.split('_')[1]

        params = {
            'market': coin,
            'side': 'ask',
            'volume': amount,
            'price': price,
            'ord_type': 'limit'
        }

        return self._private_api('POST', 'orders', params)

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        success, data, msg, time_ = self.buy(currency_pair, btc_amount)
        
        if success:
            alt_amount *= 1 - Decimal(td_fee)
            alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
            alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

            return True, alt_amount, ''
        else:
            return False, '', '[Upbit]BaseToAlt 거래에 실패했습니다[{}]'.format(msg), time_

    def get_precision(self, pair):
        return True, (-8, -8), '', 0

    async def _async_public_api(self, method, path, extra=None, header=None):
        if header is None:
            header = {}

        if extra is None:
            extra = {}
        try:
            async with aiohttp.ClientSession(headers=header) as s:
                method = method.upper()
                path = '/'.join([self._base_url, path])

                if method == 'GET':
                    rq = await s.get(path, headers=header, json=extra)
                elif method == 'POST':
                    rq = await s.post(path, headers=header, params=extra)
                else:
                    return False, '', '[{}]incorrect method'.format(method), 1

                res = json.loads(await rq.text())

                if 'error' in res:
                    return False, '', res['error']['message'], 1

                else:
                    return True, res, '', 0
        except Exception as ex:
            return False, '', 'Error [{}]'.format(ex), 1

    async def _async_private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }

        if extra is not None:
            payload.update({'query': urlencode(extra)})

        header = self._sign_generator(payload)

        return await self._async_public_api(method, path, extra, header)

    async def _get_balance(self):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('get', 'accounts')
            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_orderbook(self, symbol):
        for _ in range(3):
            success, data, message, time_ = self._async_public_api('get', 'orderbook', {'markets': symbol})
            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_deposit_addrs(self):
        for _ in range(3):
            success, data, message, time_ = self._async_public_api('get', '/'.join(['v1', 'deposits', 'coin_addresses']))
            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def _get_transaction_fee(self, currency):
        for _ in range(3):
            success, data, message, time_ = await self._async_private_api('get', '/'.join(['withdraws', 'chance']),
                                                                          {'currency': currency})
            if success:
                return True, data, message, time_

            time.sleep(time_)

        else:
            return False, '', message, time_

    async def get_deposit_addrs(self, coin_list=None):
        success, data, message, time_ = self._get_deposit_addrs()

        if not success:
            return False, '', message, time_
    
    async def get_transaction_fee(self):
        suc, currencies, msg, time_ = self.get_available_coin()

        if not suc:
            return False, '', '[Upbit] 거래가능한 코인을 가져오는 중 에러가 발생했습니다. = [{}]'.format(msg), time_

        tradable_currencies = self.service_currencies(currencies)

        fees = {}
        for currency in tradable_currencies:
            ts_suc, ts_data, ts_msg, ts_time = await self._get_transaction_fee(currency)

            if not ts_suc:
                return False, '', '[Upbit] 출금 수수료를 가져오는 중 에러가 발생했습니다. = [{}]'.format(ts_msg), ts_time

            else:
                if ts_data['currency']['withdraw_fee'] is None:
                    ts_data['currency']['withdraw_fee'] = 0

                fees[currency] = Decimal(ts_data['currency']['withdraw_fee']).quantize(Decimal(10) ** -8)

        return True, fees, '', 0

    async def get_balance(self):
        success, data, message, time_ = self._balance()

        if success:
            return {bal['currency']: bal['balance'] for bal in data}
        else:
            return False, '', '[Upbit]BaseToAlt 거래에 실패했습니다[{}]'.format(message), time_

    async def get_btc_orderbook(self, btc_sum):
        s, d, m, t = await self._get_orderbook('KRW-BTC')

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        avg_order_book = {}
        for coin in coin_list:
            coin = coin.replace('_', '-')
            suc, book, msg = await self._get_orderbook(coin)

            if not suc:
                return False, '', msg

            avg_order_book[coin] = {}

            for type_ in ['ask', 'bid']:
                order_amount, order_sum = [], 0

                for data in book[0]['orderbook_units']:
                    size = data['{}_size'.format(type_)]
                    order_amount.append(size)
                    order_sum += data['{}_price'.format(type_)] * size

                    if order_sum >= btc_sum:
                        volume = order_sum / np.sum(order_amount)
                        avg_order_book[coin]['{}s'.format(type_)] = Decimal(volume).quantize(Decimal(10) ** -8)

                        break

            return True, avg_order_book, ''

    async def compare_orderbook(self, other, coins, default_btc=1):
        upbit_res, other_res = await asyncio.gather(
            self.get_curr_avg_orderbook(coins, default_btc),
            other.get_curr_avg_orderbook(coins, default_btc)
        )

        u_suc, u_orderbook, u_msg = upbit_res
        o_suc, o_orderbook, o_msg = other_res

        if u_suc and o_suc:
            m_to_s = {}
            for currency_pair in coins:
                m_ask = u_orderbook[currency_pair]['asks']
                s_bid = o_orderbook[currency_pair]['bids']
                m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

            s_to_m = {}
            for currency_pair in coins:
                m_bid = u_orderbook[currency_pair]['bids']
                s_ask = o_orderbook[currency_pair]['asks']
                s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

            res = u_orderbook, o_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m}

            return True, res, ''


class UpbitBTC(BaseUpbit):
    def __init__(self, *args):
        super(UpbitBTC, self).__init__(*args)

    def __repr__(self):
        return 'UpbitBTC'


class UpbitKRW(BaseUpbit):
    def __init__(self, *args):
        super(UpbitKRW, self).__init__(*args)

    def __repr__(self):
        return 'UpbitKRW'

    def fee_count(self):
        return 2

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        for _ in range(3):
            success, data, message, time_ = self.sell('BTC', btc_amount)
            if success:
                break

            else:
                if '부족합니다.' in message:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
        else:
            return False, '', '[Upbit]BaseToAlt실패 = [{}]'.format(message)

        currency_pair = currency_pair.split('_')[1]

        for _ in range(3):
            success, data, message, time_ = self.buy(currency_pair, Decimal(alt_amount))

            if success:
                break

            else:
                if '부족합니다.' in message:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
        else:
            return False, '', '[Upbit]BaseToAlt실패 = [{}]'.format(message)

        alt_amount *= ((1 - Decimal(td_fee)) ** 2)
        alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return True, alt_amount, '', 0

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        currency_pair = currency_pair.split('_')[1]

        for _ in range(10):
            success, data, message, time_ = self.sell(currency_pair, alt_amount)

            if success:
                break

            else:
                if '부족합니다.' in message:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue

        else:
            return False, '', '[Upbit]AltToBase실패 = [{}]'.format(message)

        for _ in range(10):
            success, data, message, time_ = self.buy('BTC', btc_amount)

            if success:
                return True, '', '[Upbit]AltToBase ALT구매 성공', 0

            else:
                if '부족합니다.' in message:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
        else:
            return False, '', '[Upbit]AltToBase실패 = [{}]'.format(message)

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

    def buy(self, coin, amount, price=None):
        if price is None:
            success, data, message, time_ = self.get_ticker(coin)
            if not success:
                return False, '', message, time_

            price = data['ticker']

        coin = 'KRW-{}'.format(coin.split('_')[1])
        price = int(price)

        params = {
            'market': coin,
            'side': 'bid',
            'volume': str(amount),
            'price': (price * 1.05) + (self.get_step(price * 1.05) - ((price * 1.05) % self.get_step(price * 1.05))),
            'ord_type': 'limit'
        }

        return self._private_api('POST', 'orders', params)

    def sell(self, coin, amount, price=None):
        if price is None:
            success, data, message, time_ = self.get_ticker(coin)
            if not success:
                return False, '', message, time_

            price = data['ticker']

        coin = 'KRW-{}'.format(coin.split('_')[1])
        price = int(price)

        params = {
            'market': coin,
            'side': 'ask',
            'volume': str(amount),
            'price': (price * 0.95) - ((price * 0.95) % self.get_step(price * 0.95)),
            'ord_type': 'limit'
        }

        return self._private_api('POST', 'orders', params)

    async def get_trading_fee(self):
        return True, 0.0005, '', 0


class UpbitUSDT(UpbitKRW):
    def __init__(self, *args):
        super(UpbitUSDT, self).__init__(*args)

    def buy(self, coin, amount, price=None):
        if price is None:
            success, data, message, time_ = self.get_ticker(coin)
            if not success:
                return False, '', message, time_

            price = data['ticker']

        coin = 'USDT-{}'.format(coin.split('_')[1])
        price = int(price)

        params = {
            'market': coin,
            'side': 'bid',
            'volume': str(amount),
            'price': (price * 1.05) + (self.get_step(price * 1.05) - ((price * 1.05) % self.get_step(price * 1.05))),
            'ord_type': 'limit'
        }

        return self._private_api('POST', 'orders', params)

    def sell(self, coin, amount, price=None):
        if price is None:
            success, data, message, time_ = self.get_ticker(coin)
            if not success:
                return False, '', message, time_

            price = data['ticker']

        coin = 'USDT-{}'.format(coin.split('_')[1])

        price = int(price)

        params = {
            'market': coin,
            'side': 'ask',
            'volume': str(amount),
            'price': (price * 0.95) - ((price * 0.95) % self.get_step(price * 0.95)),
            'ord_type': 'limit'
        }

        return self._private_api('POST', 'orders', params)
