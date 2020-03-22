from pyinstaller_patch import *
import hmac
import json
from urllib.parse import urlencode
from decimal import *
import asyncio
import math
import aiohttp
from Exchanges.base_exchange import *


class ByBit(BaseExchange):
    def __init__(self, key, secret):
        self._endpoint = 'https://api{}.bybit.com'.format(
            '-testnet' if 'pydevd' in sys.modules else ''
        )

        self._key = key
        self._secret = secret
        self.exchange_info = None

    def servertime(self):
        suc, stat, msg, time_ = self.public_api('/v2/public/time')

        return suc, stat, msg, time_

    def encrypto(self, params):
        if params is None:
            params = {}

        suc, nonce, msg, t_sleep = self.servertime()

        if not suc:
            #  servertime값을 가져오지 못한 경우.
            return False, '', msg, t_sleep

        params.update({'timestamp': nonce['serverTime']})

        sign = hmac.new(self._secret.encode('utf-8'),
                        urlencode(sorted(params.items())).encode('utf-8'),
                        hashlib.sha256
                        ).hexdigest()

        params.update({'signature': sign})

        return True, params, msg, t_sleep

    def private_api(self, method, path, params=None):
        if params is None:
            params = {}

        try:
            suc, query, msg, time_ = self.encrypto(params)

            rq = requests.request(method, self._endpoint + path, data=query, headers={"X-MBX-APIKEY": self._key})
            res = rq.json()

            if 'msg' in res:
                return False, '', '값을 가져오는데 실패했습니다. [{}]'.format(res['msg']), 1

            else:
                return True, res, '', 1

        except Exception as ex:
            return False, '', '서버와 통신에 실패했습니다. [{}]'.format(ex), 1

    def public_api(self, path, params=None):
        if params is None:
            params = {}

        try:
            rq = requests.get(self._endpoint + path, params=params)
            res = rq.json()

            if 'msg' in res:
                return ExchangeResult(False, '', '값을 가져오는데 실패했습니다. [{}]'.format(res['msg']), 1)
            else:
                return ExchangeResult(True, res, '', 1)

        except Exception as ex:
            return ExchangeResult(False, '', '서버와 통신에 실패했습니다. [{}]'.format(ex), 1)

    def get_exchange_info(self):  # API에서 제공하는 서비스 리턴
        suc, stat, msg, time_ = self.public_api('/api/v1/exchangeInfo')

        if not suc:
            #  Symbol값을 가져오지 못한 경우.
            return suc, stat, msg, time_

        step_size = {}
        for sym in stat['symbols']:
            symbol = sym['symbol']
            market_coin = symbol[-3:]

            if 'BTC' in market_coin:
                trade_coin = symbol[:-3]
                # BNBBTC -> BTC-BNB
                coin = market_coin + '_' + trade_coin

                step_size.update({
                    coin: sym['filters'][2]['stepSize']
                })

        self.exchange_info = step_size

        return True, step_size, '', 0

    def get_step_size(self, symbol):
        if symbol == 'BTC_BCH':
            symbol = 'BTC_BCC'

        step_size = Decimal(self.exchange_info[symbol]).normalize()

        return True, step_size, '', 0

    def get_precision(self, pair):
        if pair == 'BTC_BCH':
            pair = 'BTC_BCC'

        if pair in self.exchange_info:
            return True, (-8, int(math.log10(float(self.exchange_info[pair])))), '', 0
        else:
            return False, '', '[Binance] {} 호가 정보가 없습니다.'.format(pair), 60

    def get_available_coin(self):  # API에서 제공하는 서비스 리턴
        coins = self.exchange_info.keys()
        able_coins = []
        for av in coins:
            able_coins.append(av)

        return True, able_coins, '', 0

    def buy(self, coin, amount):
        debugger.info('구매, coin-[{}] amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = coin.split('_')
        if coin[1] == 'BCH':
            coin[1] = 'BCC'

        coin = coin[1] + coin[0]
        params = {
                    'symbol': coin,
                    'side': 'buy',
                    'quantity': '{0:4f}'.format(amount).strip(),
                    'type': 'MARKET'
                  }
        buy_suc, buy_data, buy_msg, buy_time = self.private_api('POST', '/api/v3/order', params)

        if not buy_suc:
            #  구매 리퀘스트가 실패한 경우.
            debugger.debug('구매, 에러가 발생했습니다. [{}] '.format(buy_msg))
            return False, '', '[Binance]구매, 에러가 발생했습니다.[{}] '.format(buy_msg)

        return buy_suc, buy_data, buy_msg, buy_time

    def sell(self, coin, amount):
        debugger.info('판매, coin-[{}] amount-[{}] 입력되었습니다.'.format(coin, amount))

        symbol = coin.split('_')
        if symbol[1] == 'BCH':
            symbol[1] = 'BCC'

        coin = symbol[1] + symbol[0]

        params = {
                    'symbol': coin,
                    'side': 'sell',
                    'quantity': '{}'.format(amount),
                    'type': 'MARKET'
                  }

        sell_suc, sell_data, sell_msg, sell_time = self.private_api('POST', '/api/v3/order', params)

        if not sell_suc:
            #  구매 리퀘스트가 실패한 경우.
            debugger.debug('판매, 에러가 발생했습니다. [{}] '.format(sell_msg))
            return False, '', '[Binance]판매, 에러가 발생했습니다.[{}] '.format(sell_msg)

        return sell_suc, sell_data, sell_msg, sell_time

    def fee_count(self):
        return 1

    def bnc_btm_quantizer(self, symbol):
        binance_qtz = self.get_step_size(symbol)[1]
        return Decimal(10) ** -4 if binance_qtz < Decimal(10) ** -4 else binance_qtz

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        # btc sell alt buy
        suc, data, msg, time_ = self.buy(currency_pair, alt_amount)

        if not suc:
            # Base to alt 실패시
            debugger.info('BaseToAlt에러 = [{}]'.format(msg))

            return suc, data, msg, time_

        coin = currency_pair.split('_')[1]
        # 보내야하는 alt의 양 계산함.
        alt_amount *= 1 - Decimal(td_fee)
        alt_amount -= Decimal(tx_fee[coin])
        alt_amount = alt_amount.quantize(self.bnc_btm_quantizer(currency_pair), rounding=ROUND_DOWN)

        return True, alt_amount, '', 0

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        for _ in range(10):
            suc, data, msg, time_ = self.sell(currency_pair, alt_amount)

            if suc:
                debugger.info('AltToBase 성공')

                return True, '', data, 0

            else:
                time.sleep(time_)

        else:
            return False, '', '[Binance]AltToBase실패 = [{}]'.format(msg)

    def get_ticker(self):
        suc, data, msg, time_ = self.public_api('/api/v1/ticker/24hr')

        return suc, data, msg, time_

    def withdraw(self, coin,amount, to_address, payment_id=None):
        debugger.debug('출금-[{}][{}][{}][{}] 받았습니다.'.format(coin, amount, to_address, payment_id))
        if coin == 'BCH':
            coin = 'BCC'
        params = {
                    'asset': coin,
                    'address': to_address,
                    'amount': '{}'.format(amount),
                    'name': 'SAICDiffTrader'
                }

        if payment_id:
            tag_dic = {'addressTag': payment_id}
            params.update(tag_dic)

        suc, data, msg, time_ = self.private_api('POST', '/wapi/v3/withdraw.html', params)

        if not suc:
            debugger.debug('withdraw 에러 발생 [{}]'.format(msg))

        return suc, data, msg, time_

    def get_candle(self, coin, unit, count):
        path = '/v2/public/kline/list'

        params = {
            'symbol': coin,
            'interval': '{}'.format(unit),
            'from': int(time.time()),
            'limit': count
        }
        # 1 3 5 15 30 60 120 240 360 720 "D" "M" "W" "Y"
        result = self.public_api(path, params)

        if result.success is False:
            return result

        history = {
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': [],
            'timestamp': [],
        }

        try:
            for info in result.data:
                history['open'].append(info.get('open'))
                history['high'].append(info.get('high'))
                history['low'].append(info.get('low'))
                history['close'].append(info.get('close'))
                history['volume'].append(info.get('volume'))
                history['timestamp'].append(info.get('open_time'))

            return ExchangeResult(True, history, '')

        except Exception as ex:
            return ExchangeResult(
                False,
                '',
                'history를 가져오는 과정에서 에러가 발생했습니다. =[{}]'.format(ex)
            )

    async def async_private_api(self, method, path, params=None):
        if params is None:
            params = {}

        async with aiohttp.ClientSession(headers={"X-MBX-APIKEY": self._key}) as s:
            crypto_suc, query, crypto_msg, crypto_time = self.encrypto(params)

            if not crypto_suc:
                return crypto_suc, query, crypto_msg, crypto_time

            try:
                if method == 'GET':
                    sig = query.pop('signature')
                    query = "{}&signature={}".format(urlencode(sorted(params.items())), sig)
                    rq = await s.get(self._endpoint + path + "?{}".format(query))

                else:
                    rq = await s.post(self._endpoint + path, data=query)

                res = await rq.text()
                res = json.loads(res)

                if 'msg' in res:
                    return False, res, '값을 불러오지 못했습니다. [{}]'.format(res['msg']), 1

                else:
                    return True, res, '', 0

            except Exception as ex:
                return False, '', '서버와의 통신에 실패했습니다. [{}]'.format(ex), 1

    async def async_public_api(self, path, params=None):
        if params is None:
            params = {}

        async with aiohttp.ClientSession() as s:
            rq = await s.get(self._endpoint + path, params=params)

        try:
            res = await rq.text()
            res = json.loads(res)

            if 'msg' in res:
                return False, '', '값을 불러오지 못했습니다. [{}]'.format(res['msg']), 1

            else:
                return True, res, '', 0

        except Exception as ex:
            return False, '', '서버와의 통신에 실패했습니다. [{}]'.format(ex), 1

    async def get_deposit_addrs(self):
        av_suc, coin_list, av_msg, av_time = self.get_available_coin()

        if not av_suc:
            return av_suc, coin_list, av_msg, av_time

        try:
            ret_msg = ""
            rq_dic = {}
            coin_list.append('BTC_BTC')  # ? 왜 넣었지?

            for coin in coin_list:
                coin = coin.split('_')[1]
                if coin == 'BCH':
                    coin = 'BCC'

                rq_suc, rq_data, rq_msg, rq_time = await self.async_private_api('GET','/wapi/v3/depositAddress.html',{'asset': coin})

                if not rq_data['success']:
                    debugger.debug(rq_msg)
                    debugger.info('[{}]해당 코인은 점검 중입니다.'.format(coin))
                    ret_msg += '[{}]해당 코인은 점검 중입니다.\n'.format(coin)
                    continue

                rq_dic[coin] = rq_data['address']

                try:
                    # Tag가 없는경우 'addressTag'값 자체가 존재하지 않음
                    tag = rq_data['addressTag']

                except:
                    tag = ''

                if tag:
                    rq_dic[coin + 'TAG'] = tag

            return True, rq_dic, ret_msg, 0

        except Exception as ex:
            return False, '', '[Binance]입금 주소를 가져오는데 실패했습니다. [{}]'.format(ex), 1

    async def get_avg_price(self,coins): # 내거래 평균매수가
        try:
            amount_price_list, res_value = [], []
            for coin in coins:
                total_price, bid_count, total_amount = 0, 0, 0

                for _ in range(10):
                    hist_suc, history, hist_msg, hist_time = await self.async_public_api(
                        '/api/v3/allOrders', {'symbol': coin})

                    if hist_suc:
                        break

                    else:
                        debugger.debug('History값을 가져오는데 실패했습니다. [{}]'.format(hist_msg))
                        time.sleep(1)

                else:
                    # history 값을 가져오는데 실패하는 경우.
                    return (hist_suc, history,
                            '[Binance]History값을 가져오는데 실패했습니다. [{}]'.format(hist_msg), hist_time)

                history.reverse()
                for _data in history:
                    side = _data['side']
                    n_price = float(_data['price'])
                    price = Decimal(n_price - (n_price * 0.1)).quantize(Decimal(10) ** -6)
                    amount = Decimal(_data['origQty']).quantize(Decimal(10) ** -6)
                    if side == 'BUY':
                        amount_price_list.append({
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
                        amount_price_list.pop(0)

                _values = {coin: {
                    'avg_price': total_price / bid_count,
                    'coin_num': total_amount
                }}
                res_value.append(_values)

            return True, res_value, '', 0

        except Exception as ex:
            return False, '', '[Binance]평균 값을 가져오는데 실패했습니다. [{}]'.format(ex), 1

    async def get_trading_fee(self): #Binance는 trade_fee가 0.1로 되어있음.
        return True, 0.001, '', 0

    async def get_transaction_fee(self):
        fees = {}
        try:
            async with aiohttp.ClientSession() as s:
                try:
                    rq = await s.get('https://www.binance.com/assetWithdraw/getAllAsset.html')
                    data_list = await rq.text()
                    data_list = json.loads(data_list)

                    if not data_list:
                        # AllAsset에서 값을 못받아 온 경우.
                        debugger.debug('get_transaction_fee 에러 발생 [{}]'.format(rq))

                        return False, '', '[Binance]출금비용을 가져오는데 실패했습니다.', 60
                except Exception as ex:
                    return False, '', '[Binance]출금비용을 가져오는데 실패했습니다. [{}]'.format(ex), 60

            for f in data_list:
                if f['assetCode'] == 'BCC':
                    f['assetCode'] = 'BCH'
                # fees[BNB] = 어쭈구
                fees[f['assetCode']] = Decimal(f['transactionFee']).quantize(Decimal(10)**-8)

            return True, fees, '', 0

        except Exception as ex:
            return False, '', '[Binance]출금비용을 가져오는데 실패했습니다. [{}]'.format(ex), 60

    async def balance(self):
        suc, data, msg, time_ = await self.async_private_api('GET', '/api/v3/account')

        if not suc:
            return suc, data, msg, time_

        balance = {}
        for bal in data['balances']:
            if bal['asset'] == 'BCC':
                bal['asset'] = 'BCH'

            if float(bal['free']) > 0:
                balance[bal['asset'].upper()] = float(bal['free'])  # asset-> 코인이름 free -> 거래가능한 코인수

        return True, balance, '', 0

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):  # 상위 평균매도/매수가 구함
        try:
            avg_order_book = {}
            for currency_pair in coin_list:
                if currency_pair == 'BTC_BTC':
                    continue

                sp = currency_pair.split('_')
                coin = sp[1] + sp[0]

                dep_suc, book, dep_msg, dep_time = await self.async_public_api('/api/v1/depth', {'symbol': coin})

                if not dep_suc:
                    return dep_suc, book, dep_msg, dep_time

                avg_order_book[currency_pair] = {}
                for type_ in ['asks', 'bids']:
                    order_amount, order_sum = 0, 0

                    for data in book[type_]:
                        order_amount += Decimal(data[1])  # 0 - price 1 - qty
                        order_sum += (Decimal(data[0]) * Decimal(data[1])).quantize(Decimal(10) ** -8)
                        if order_sum >= Decimal(btc_sum):
                            _v = ((order_sum / order_amount).quantize(Decimal(10) ** -8))
                            avg_order_book[currency_pair][type_] = _v
                            break

            return True, avg_order_book, '', 0
        except Exception as ex:
            return False, '', 'get_curr_avg_orderbook_error[{}]'.format(ex), 1

    async def compare_orderbook(self, other, coins, default_btc=1):
        for _ in range(3):
            binance_res, other_res = await asyncio.gather(
                self.get_curr_avg_orderbook(coins, default_btc),
                other.get_curr_avg_orderbook(coins, default_btc)
            )

            binance_suc, binance_avg_orderbook, binance_msg, binance_times = binance_res
            other_suc, other_avg_orderbook, other_msg, other_times = other_res

            if 'BTC' in coins:
                # 나중에 점검
                coins.remove('BTC')

            if binance_suc and other_suc:
                m_to_s = {}
                for currency_pair in coins:
                    m_ask = binance_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in coins:
                    m_bid = binance_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                res = binance_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m}

                return True, res, '', 0

            else:
                time.sleep(binance_times)
                continue

        if not binance_suc or not other_suc:
            return False, '', 'binance_error-[{}] other_error-[{}]'.format(binance_msg, other_msg), binance_times
