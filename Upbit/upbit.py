import jwt

from BaseExchange import BaseExchange


class BaseUpbit(BaseExchange):
    '''

    '''
    
    def __init__(self, key, secret, coin_list):
        self._base_url = 'https://api.upbit.com/v1'
        if kwargs:
            self._key = key
            self._secret = secret
        self._coin_list = coin_list
    
    def _set_orderbook_setting(self):
        pass
    
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
            return False, '', '[{}]incorrect method'.format(method)
        
        try:
            res = rq.json()
            
            if 'error' in res:
                return False, '', res['error']['message']
            
            else:
                return True, res, ''
        
        except Exception as ex:
            return False, '', 'Error [{}]'.format(ex)
    
    def _private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }
        
        if extra is not None:
            payload.update({'query': urlencode(extra)})
        
        header = self.get_jwt_token(payload)
        
        return self._public_api(method, path, extra, header)
    
    def _sign_generator(self, *args):
    
    def fee_count(self):
        # 몇변의 수수료가 산정되는지
        return 1
    
    def get_jwt_token(self, payload):
        return 'Bearer {}'.format(jwt.encode(payload, self._secret, ).decode('utf8'))
    
    def get_ticker(self, market):
        return self._public_api('get', 'ticker', market)
    
    def currencies(self):
        # using get_currencies, service_currencies
        return self._public_api('get', '/'.join(['market', 'all']))
    
    def get_currencies(self, currencies):
        res = []
        return [res.append(data['market']) for data in currencies if not currencies['market'] in res]
    
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
    
    def buy(self, coin, amount, price):
        amount, price = map(str, (amount, price * 1.05))
        
        params = {
            'market': coin,
            'side': 'bid',
            'volume': amount,
            'price': price,
            'ord_type': 'limit'
        }
        
        return self._private_api('POST', 'orders', params)
    
    def sell(self, coin, amount, price):
        amount, price = map(str, (amount, price * 0.95))
        
        params = {
            'market': coin,
            'side': 'ask',
            'volume': amount,
            'price': price,
            'ord_type': 'limit'
        }
        
        return self._private_api('POST', 'orders', params)
    
    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        # after self.buy()
        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)
        
        return True, alt_amount, ''
    
    # def alt_to_base(self, currency_pair, btc_amount, alt_amount):
    #     # after self.sell()
    #     if suc:
    #         upbit_logger.info('AltToBase 성공')
    #
    #         return True, '', data, 0
    #
    #     else:
    #         upbit_logger.info(msg)
    #
    #         if '부족합니다.' in msg:
    #             alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
    #             continue
    
    async def async_public_api(self, method, path, extra=None, header=None):
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
                    return False, '', '[{}]incorrect method'.format(method)
                
                res = json.loads(await rq.text())
                
                if 'error' in res:
                    return False, '', res['error']['message']
                
                else:
                    return True, res, ''
        except Exception as ex:
            return False, '', 'Error [{}]'.format(ex)
    
    async def async_private_api(self, method, path, extra=None):
        payload = {
            'access_key': self._key,
            'nonce': int(time.time() * 1000),
        }
        
        if extra is not None:
            payload.update({'query': urlencode(extra)})
        
        header = self.get_jwt_token(payload)
        
        return await self.async_public_api(method, path, extra, header)
    
    async def get_deposit_addrs(self, coin_list=None):
        return self.async_public_api('get', '/'.join(['v1', 'deposits', 'coin_addresses']))
    
    async def get_balance(self):
        return self._private_api('get', 'accounts')
    
    async def get_detail_balance(self, data):
        # bal = self.get_balance()
        return {bal['currency']: bal['balance'] for bal in data}
    
    async def get_orderbook(self, market):
        return self.async_public_api('get', 'orderbook', {'markets': market})
    
    async def get_btc_orderbook(self, btc_sum):
        s, d, m = await self.get_orderbook('KRW-BTC')
    
    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        avg_order_book = {}
        for coin in coin_list:
            coin = coin.replace('_', '-')
            suc, book, msg = await self.get_orderbook(coin)
            
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

