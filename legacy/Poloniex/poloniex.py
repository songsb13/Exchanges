import sys
import time
import hmac
import hashlib
import requests
import json
import websocket
import logging
from threading import Thread
from urllib.parse import urlencode
from datetime import datetime
import pytz
from operator import itemgetter
from decimal import *
import asyncio

if 'pydevd' not in sys.modules:
    from .models import AvgPrice

logger = logging.getLogger(__name__)


class Poloniex:
    def __init__(self, key, secret):
        self._key = key
        self._secret = secret

    def trading_api(self, command, extra_parameters={}):
        req = {}
        url = 'https://poloniex.com/tradingApi'
        req['command'] = command
        req['nonce'] = int(time.time() * 1000000)
        req.update(extra_parameters)

        post_data = urlencode(req)

        sign = hmac.new(self._secret.encode(), post_data.encode(), hashlib.sha512).hexdigest()
        headers = {
            'Sign': sign,
            'Key': self._key
        }

        ret = requests.post(url, data=req, headers=headers)
        j_ret = ret.json()

        logger.debug('Poloniex-Trading API[{}, {}]-{}'.format(command, extra_parameters, j_ret))

        return j_ret

    def public_api(self, command, extra_parameters={}):
        url = 'https://poloniex.com/public?command={}'.format(command)
        for k, v in extra_parameters.items():
            url += '&{}={}'.format(k, v)

        ret = requests.get(url)
        j_ret = ret.json()

        logger.debug('Poloniex-Public API[{}, {}]-{}'.format(command, extra_parameters, j_ret))

        return j_ret

    def push_api(self, on_message):
        def on_open(ws):
            _ws.send(json.dumps({'command': 'subscribe', 'channel': 1002}))

        def on_error(ws, error):
            logger.error(error)

        def on_close(ws):
            if _t._running:
                try:
                    stop()
                except Exception as e:
                    logger.exception(e)
                try:
                    start()
                except Exception as e:
                    logger.exception(e)
                    stop()
            else:
                logger.info("Websocket closed!")

        def start():
            """ Run the websocket in a thread """
            _t = Thread(target=_ws.run_forever)
            _t.daemon = True
            _t._running = True
            _t.start()
            logger.info('Websocket thread started')

            return _t

        def stop():
            """ Stop/join the websocket thread """
            _t._running = False
            _ws.close()
            _t.join()
            logger.info('Websocket thread stopped/joined')

        _ws = websocket.WebSocketApp("wss://api2.poloniex.com/",
                                     on_open=on_open,
                                     on_message=on_message,
                                     on_error=on_error,
                                     on_close=on_close)

        _t = start()

        return _t

    def get_current_prices(self):
        tick = {}

        iniTick = self.public_api('returnTicker')
        _ids = {market: iniTick[market]['id'] for market in iniTick}
        for market in iniTick:
            tick[_ids[market]] = iniTick[market]

        def on_message(ws, message):
            message = json.loads(message)
            if 'error' in message:
                return logger.error(message['error'])

            if message[0] == 1002:
                if message[1] == 1:
                    return logger.info('Subscribed to ticker')

                if message[1] == 0:
                    return logger.info('Unsubscribed to ticker')

                data = message[2]
                data = [Decimal(dat) for dat in data]
                tick[data[0]] = {'id': data[0],
                                 'last': data[1],
                                 'lowestAsk': data[2],
                                 'highestBid': data[3],
                                 'percentChange': data[4],
                                 'baseVolume': data[5],
                                 'quoteVolume': data[6],
                                 'isFrozen': data[7],
                                 'high24hr': data[8],
                                 'low24hr': data[9]
                                 }

        self.push_api(on_message)

        return tick, _ids

    def get_balance(self):
        j_ret = self.trading_api("returnCompleteBalances")
        ret_dict = {}
        for key, val in j_ret.items():
            if float(val['btcValue']) > 0:
                ret_dict[key] = val
        return ret_dict

    def get_avg_price(self, coins, margin=False):
        ret_dict = {}
        getcontext().prec = 8
        extra_parameter = {}

        db_avg_prices = AvgPrice.objects.filter(pkey=self._key, is_margin=margin).order_by('-last_update')
        # if db is empty
        if not db_avg_prices:
            extra_parameter["start"] = 0
        else:
            # TODO
            # smallest timestamp as start
            pass

        # TODO
        #  if j_ret is more than 10,000 items, need to query again with next timestamp
        extra_parameter["currencyPair"] = "all"
        j_ret = self.trading_api("returnTradeHistory", extra_parameter)
        for coin in coins:
            coin_name = 'BTC_{}'.format(coin)
            saved_data = AvgPrice.objects.filter(pkey=self._key,
                                                 coin_name=coin_name,
                                                 is_margin=margin).order_by('-last_update')
            if coin_name in j_ret:
                if not saved_data:
                    db_val = AvgPrice(pkey=self._key, coin_name=coin_name, is_margin=margin)
                    last_update = datetime(1900, 1, 1, tzinfo=pytz.utc)
                    coin_histories = []
                else:
                    db_val = saved_data[0]
                    last_update = db_val.last_update
                    coin_histories = [[db_val.avg_price, db_val.coin_num]]

                sorted_history = sorted(j_ret[coin_name], key=itemgetter('date'))
                for history in sorted_history:
                    aware_history_dt = datetime.strptime(history['date'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)
                    if aware_history_dt <= last_update:
                        continue

                    if margin:
                        pass
                    else:
                        if history['category'] == 'exchange':
                            if history['type'] == 'buy':
                                coin_histories.append([Decimal(history['rate']) * (1 + Decimal(history['fee'])),
                                                       Decimal(history['amount']) * (1 - Decimal(history['fee']))])
                            elif history['type'] == 'sell':
                                # subtract sell from buy
                                for idx, coin_history in enumerate(coin_histories):
                                    coin_history[1] -= Decimal(history['amount'])
                                    if coin_history[1] < 0:
                                        history['amount'] = -coin_history[1]
                                    else:
                                        break

                                # pop empty buy history
                                coin_histories = coin_histories[idx:]

                total_price = Decimal(0.0)
                coin_num = Decimal(coins[coin]['available'])
                for coin_history in coin_histories:
                    total_price += coin_history[0] * coin_history[1]
                avg_price = (total_price / coin_num).quantize(Decimal(10) ** -8)
                print('{} - {}'.format(coin_name, avg_price))
                db_val.last_update = aware_history_dt
                db_val.avg_price = avg_price
                db_val.coin_num = coin_num
                db_val.save()

                ret_dict[coin] = {'avg_price': avg_price, 'coin_num': coin_num}
            else:
                # Trade history does not exit
                if not saved_data:
                    ret_dict[coin] = {'avg_price': Decimal(0.00000000), 'coin_num': coins[coin]['available']}
                else:
                    db_val = saved_data[0]
                    ret_dict[coin] = {'avg_price': db_val.avg_price, 'coin_num': coins[coin]['available']}

        return json.dumps(ret_dict)

    def get_curr_avg_orderbook(self, currency_pairs, btc_sum=1):
        """
        :param currency_pairs:  list of strings in BTC_XXX form / ex) ['BTC_ETH', 'BTC_XRP']
        :param btc_sum: any positive number
        :return: average order book
        """
        orderbook = self.public_api('returnOrderBook', {'currencyPair': 'all', 'depth': 100})
        avg_orderbook = {}
        for k, v in orderbook.items():
            if k in currency_pairs:
                avg_orderbook[k] = {}
                for order_type in ['asks', 'bids']:
                    sum = Decimal(0.0)
                    total_coin_num = Decimal(0.0)
                    for price, alt_coin_num in v[order_type]:
                        sum += Decimal(price) * Decimal(alt_coin_num)
                        total_coin_num += Decimal(alt_coin_num)
                        if sum > btc_sum:
                            break
                    avg_orderbook[k][order_type] = (sum/total_coin_num).quantize(Decimal(10) ** -8)

        return avg_orderbook

    def buy_coin(self, coin_name, amount):
        tick = self.public_api('returnTicker')
        parameters = {}
        parameters['currency_pair'] = coin_name
        parameters['rate'] = float(tick[coin_name]['lowestAsk']) * 1.05
        parameters['amount'] = amount

        res = self.trading_api('buy', parameters)

        # TODO
        # save them to DB
        order_num = res['orderNumber']
        amount_bought = res['resultingTrades']['amount']
        date_bought = res['resultingTrades']['date']
        rate_bought = res['resultingTrades']['rate']
        total_bought = res['resultingTrades']['total']

        return res

    def sell_coin(self, coin_name, amount):
        tick = self.public_api('returnTicker')
        parameters = {}
        parameters['currency_pair'] = coin_name
        parameters['rate'] = float(tick[coin_name]['highestBid']) * 0.95
        parameters['amount'] = amount

        res = self.trading_api('sell', parameters)

        # TODO
        # save them to DB
        order_num = res['orderNumber']
        amount_sold = res['resultingTrades']['amount']
        date_sold = res['resultingTrades']['date']
        rate_sold = res['resultingTrades']['rate']
        total_sold = res['resultingTrades']['total']

        return res

    def trading_fee(self):
        res = self.trading_api("returnFeeInfo")

        # we only trade with market price which pays taker fee.
        return res['takerFee']

    def transaction_fee(self, currency_code='BTC'):
        res = self.public_api("returnCurrencies")

        return res[currency_code]['txFee']

    def tradable_currencies(self):
        res = self.public_api("returnCurrencies")

        return ["BTC_"+currency.upper() for currency in res]

    def get_deposit_addrs(self):
        res = self.trading_api('returnDepositAddresses')

        return res

    def withdraw(self, coin, amount, to_address, payment_id=None):
        extra_parameter = {
            "currency": coin,
            "amount": amount,
            "address": to_address
        }
        if payment_id is not None:
            extra_parameter.update({'paymentId': payment_id})

        res = self.trading_api('withdraw', extra_parameter)
        return res

    async def poloniex__korbit(self, korbit, default_btc):
        korbit_currency_pair = korbit.korbit_available_coin()

        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, self.get_curr_avg_orderbook, korbit_currency_pair, default_btc)
        poloniex_avg_orderbook = await fut

        korbit_avg_orderbook = {}
        for currency_pair in korbit_currency_pair:
            fut = loop.run_in_executor(None, korbit.korbit_average_upper_bids_lower_asks, default_btc, currency_pair)
            data = await fut
            korbit_avg_orderbook[currency_pair] = list(data.values())[0]

        # buy from poloniex -> sell to korbit
        p_to_k = {}
        for currency_pair in korbit_currency_pair:
            p_ask = poloniex_avg_orderbook[currency_pair]['asks']
            k_bid = korbit_avg_orderbook[currency_pair]['bids']
            p_to_k[currency_pair] = float(((p_ask - k_bid) / p_ask).quantize(Decimal(10)**-8))

        # buy from korbit -> sell to poloniex
        k_to_p = {}
        for currency_pair in korbit_currency_pair:
            p_bid = poloniex_avg_orderbook[currency_pair]['bids']
            k_ask = korbit_avg_orderbook[currency_pair]['asks']
            k_to_p[currency_pair] = float(((p_bid - k_ask) / p_bid).quantize(Decimal(10)**-8))

        return {'p_to_k': p_to_k, 'k_to_p': k_to_p}



