from pyinstaller_patch import *
import hmac
import json
from urllib.parse import urlencode
from decimal import *
import asyncio
import math
import aiohttp
from datetime import datetime, timezone
from Exchanges.base_exchange import *


class ByBit(BaseExchange):
    def __init__(self, key, secret):
        self._endpoint = 'https://api{}.bybit.com'.format(
            '-testnet' if 'pydevd' in sys.modules else ''
        )

        self._key = key
        self._secret = secret
        self.exchange_info = None
        self._get_exchange_info()

        ExchangeResult.set_exchange_name = 'ByBit'

    def servertime(self):
        return self.public_api('/v2/public/time')

    def encrypto(self, params):
        if params is None:
            params = {}

        servertime_result = self.servertime()

        if servertime_result.success is False:
            #  servertime값을 가져오지 못한 경우.
            return servertime_result

        params.update({'timestamp': int(float(servertime_result.data) * 1000)})
        params.update({'api_key': self._key})
        params.update({'recv_window': 10000})

        _val = '&'.join(
            [str(k) + "=" + str(v) for k, v in sorted(params.items()) if (k != 'sign') and (v is not None)])
        sign = str(hmac.new(bytes(self._secret, "utf-8"), bytes(_val, "utf-8"), digestmod="sha256").hexdigest())

        params.update({'sign': sign})

        return ExchangeResult(True, params, '')

    def private_api(self, method, path, params=None):
        if params is None:
            params = {}

        try:
            sign_result = self.encrypto(params)

            if method.upper() == 'GET':
                rq = requests.get(self._endpoint + path, params=sign_result.data)
            else:
                rq = requests.post(self._endpoint + path, data=sign_result.data)
            res = rq.json()

            if res['ret_msg'].lower() != 'ok':
                debugger.debug('{} - {}'.format(path, sign_result.data))
                return ExchangeResult(False, res, '값을 불러오지 못했습니다. [{}]'.format(res['ret_msg']), 1)
            else:
                return ExchangeResult(True, res['result'], '')

        except Exception as ex:
            return ExchangeResult(False, '', '서버와 통신에 실패했습니다. [{}]'.format(ex), 1)

    def public_api(self, path, params=None):
        if params is None:
            params = {}

        try:
            rq = requests.get(self._endpoint + path, params=params)
            res = rq.json()

            if res['ret_msg'] != 'OK':
                return ExchangeResult(False, '', '값을 가져오는데 실패했습니다. [{}]'.format(res['ret_msg']), 1)
            else:
                if '/time' in path:
                    return ExchangeResult(True, res['time_now'], '')
                return ExchangeResult(True, res['result'], '')

        except Exception as ex:
            return ExchangeResult(False, '', '서버와 통신에 실패했습니다. [{}]'.format(ex), 1)

    def _get_exchange_info(self):  # API에서 제공하는 서비스 리턴
        result = self.public_api('/v2/public/symbols')

        if result.success is False:
            #  Symbol값을 가져오지 못한 경우.
            return result

        step_size = {}
        for sym in result.data:
            market_coin = sym.get('quote_currency')
            trade_coin = sym.get('base_currency')
            coin = market_coin + '_' + trade_coin

            step_size.update({
                coin: sym['price_filter']['tick_size']
            })

        self.exchange_info = step_size

        return ExchangeResult(True, step_size, '')

    def get_market_from_symbol(self, symbol):
        # bybit does not have market
        return symbol.split('_')[1]

    def get_step_size(self, symbol):
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
        coins = list(self.exchange_info.keys())

        return ExchangeResult(True, coins, '')

    def get_order_history(self, order_id):
        path = '/open-api/order/list'
        order_history_result = self.private_api('GET', path, {'order_id': order_id})
        if order_history_result.success is False:
            return order_history_result

        # TODO
        # return all history, and let caller choose necessary info
        data = order_history_result.data['data'][0]
        order_history_result.data = dict(
            price=data['price'],
            amount=data['qty'],
            symbol='_'.join([data['symbol'][3:], data['symbol'][:3]]),
            exec_time=datetime.strptime(
                data['created_at'], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=timezone.utc)
        )
        return order_history_result

    def buy(self, coin, amount, price=None):
        debugger.info('구매, coin-[{}] amount-[{}] 입력되었습니다.'.format(coin, amount))
        coin = coin.split('_')

        coin = coin[1] + coin[0]
        params = {
            'symbol': coin,
            'side': 'Buy',
            'qty': amount,
            'order_type': 'Market',
            'time_in_force': 'GoodTillCancel'
        }
        buy_result = self.private_api('POST', '/v2/private/order/create', params)

        if buy_result.success is False:
            debugger.debug('구매, 에러가 발생했습니다. [{}] '.format(buy_result.message))
            return ExchangeResult(False, '', '[ByBit] 구매, 에러가 발생했습니다.[{}] '.format(buy_result.message))

        return buy_result

    def sell(self, coin, amount, price=None):
        debugger.info('판매, coin-[{}] amount-[{}] 입력되었습니다.'.format(coin, amount))

        symbol = coin.split('_')
        coin = symbol[1] + symbol[0]

        params = {
            'symbol': coin,
            'side': 'Sell',
            'qty': amount,
            'order_type': 'Market',
            'time_in_force': 'GoodTillCancel'
        }
        buy_result = self.private_api('POST', '/v2/private/order/create', params)

        if buy_result.success is False:
            debugger.debug('판매, 에러가 발생했습니다. [{}] '.format(buy_result.message))
            return ExchangeResult(False, '', '[ByBit] 판매, 에러가 발생했습니다.[{}] '.format(buy_result.message))

        return buy_result

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

    def get_ticker(self, symbol):
        market, coin = symbol.split('_')
        symbol = (coin+market).upper()
        ticker_result = self.public_api('/v2/public/tickers', {'symbol': symbol})
        ticker_result.data = Decimal(ticker_result.data[0]['last_price']).quantize(Decimal(10) ** -8)

        return ticker_result

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

        market, coin = coin.split('_')
        symbol = (coin+market).upper()
        if count >= 200:
            count = 199

        # do +1 since sometimes data is missing
        params = {
            'symbol': symbol,
            'interval': '{}'.format(unit),
            'from': int(time.time()) - (unit * 60) * (count +1),
            'limit': (count + 1)
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
            for info in result.data[-count:]:
                history['open'].append(float(info.get('open')))
                history['high'].append(float(info.get('high')))
                history['low'].append(float(info.get('low')))
                history['close'].append(float(info.get('close')))
                history['volume'].append(float(info.get('volume')))
                history['timestamp'].append(info.get('open_time'))

            return ExchangeResult(True, history, '')

        except Exception as ex:
            debugger.exception("FATAL")
            return ExchangeResult(
                False,
                '',
                'history를 가져오는 과정에서 에러가 발생했습니다. =[{}]'.format(ex)
            )

    async def async_private_api(self, method, path, params=None):
        if params is None:
            params = {}

        async with aiohttp.ClientSession() as s:
            sign_result = self.encrypto(params)

            if sign_result.success is False:
                return sign_result

            try:
                if method == 'GET':
                    query = urlencode(sorted(sign_result.data.items()))
                    rq = await s.get(self._endpoint + path + "?{}".format(query))

                else:
                    rq = await s.post(self._endpoint + path, data=sign_result.data)

                res = await rq.text()
                res = json.loads(res)

                if res['ret_msg'] != 'OK':
                    return ExchangeResult(False, res, '값을 불러오지 못했습니다. [{}]'.format(res['ret_msg']), 1)
                else:
                    return ExchangeResult(True, res['result'], '')

            except Exception as ex:
                return ExchangeResult(False, '', '서버와의 통신에 실패했습니다. [{}]'.format(ex), 1)

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
        balance = {}
        for coin in ['BTC', 'ETH', 'XRP', 'EOS']:
            balance_result = await self.async_private_api('GET', '/v2/private/wallet/balance', {'coin': coin})

            if balance_result.success is False:
                return balance_result

            for key, bal in balance_result.data.items():

                if float(bal['wallet_balance']) > 0:
                    balance[key.upper()] = float(bal['wallet_balance'])

        return ExchangeResult(True, balance, '')

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
