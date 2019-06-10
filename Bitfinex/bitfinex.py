from pyinstaller_patch import *
import hmac
import json
import websocket
from threading import Thread
from decimal import *
import asyncio
import base64


class Bitfinex:
    def __init__(self, key, secret):
        self._key = key
        self._secret = secret
        self._tx_fee = {}
        self.symbols = {}

    def fee_count(self):
        return 1

    def trading_api(self, command, extra_parameters={}):
        req = {}
        url = 'https://api.bitfinex.com/v1/{}'.format(command)

        req['request'] = '/v1/{}'.format(command)
        req['nonce'] = str(time.time() * 1000)
        req.update(extra_parameters)

        post_data = base64.b64encode(json.dumps(req).encode())

        sign = hmac.new(self._secret.encode(), post_data, hashlib.sha384).hexdigest()
        headers = {
            'X-BFX-APIKEY': self._key,
            'X-BFX-PAYLOAD': post_data,
            'X-BFX-SIGNATURE': sign
        }

        try:
            ret = requests.post(url, data=req, headers=headers)
            debugger.debug(
                'Bitfinex-Trading API[{}, {}]- {} -{}'.format(command, extra_parameters, ret.status_code, ret.text))
            j_ret = ret.json()
            if ret.status_code == 400:
                debugger.debug(ret.text)
                if 'message' in j_ret and 'Nonce is too small' in j_ret['message']:
                    return False, '', 'Bitfinex API와 통신에 실패하였습니다.', 1
                elif 'message' in j_ret:
                    return (False, '',
                            'Bitfinex API와 통신에 실패하였습니다. - [{}]'.format(j_ret['message']), 0)
                else:
                    return False, '', 'Bitfinex API와 통신에 실패하였습니다.', 0
            elif 'error' in j_ret and j_ret['error'] == 'ERR_RATE_LIMIT':
                return False, '', 'Bitfinex API 조회가능 횟수를 초과하였습니다.', 10
            elif 'error' in j_ret:
                debugger.debug(ret.text)
                return False, '', 'Bitfinex API 오류입니다.', 0
        except:
            return False, '', '네트워크 상태가 불안정합니다.', 10

        return True, j_ret, '', 0

    def public_api(self, command, extra_parameters={}):
        url = 'https://api.bitfinex.com/v1/{}'.format(command)
        for k, v in extra_parameters.items():
            url += '/{}'.format(v)

        while True:
            try:
                ret = requests.get(url)
                debugger.debug('Bitfinex-Public API[{}, {}]- {} -{}'.format(command, extra_parameters, ret.status_code,
                                                                            ret.text))
                if ret.status_code == 520:
                    continue

                j_ret = ret.json()
                if 'error' in j_ret and j_ret['error'] == 'ERR_RATE_LIMIT':
                    return False, '', 'Bitfinex API 조회가능 횟수를 초과하였습니다.', 10

                break
            except:
                time.sleep(10)

        return True, j_ret, '', 0

    def push_api(self, on_message, extra_parameters={}):
        def on_open(ws):
            params = {'command': 'subscribe', 'channel': "ticker"}
            params.update(extra_parameters)
            _ws.send(json.dumps(params))

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

        _ws = websocket.WebSocketApp("wss://api.bitfinex.com/ws",
                                     on_open=on_open,
                                     on_message=on_message,
                                     on_error=on_error,
                                     on_close=on_close)

        _t = start()

        return _t

    def get_current_price(self, currency_pair):
        bitfinex_currency_pair = (currency_pair.split('_')[-1] + currency_pair.split('_')[0]).lower()
        try:
            price = self.public_api('pubticker', {'pair': bitfinex_currency_pair})
            current_price = float(price['last_price'])
        except:
            debugger.exception('FATAL')
            return False, '', "알 수 없는 오류. 개발자에게 로그를 보내주세요", 5

        return True, current_price, "", 0

    async def balance(self):
        success, j_ret, msg, st = self.trading_api("balances")
        if not success:
            return success, '', msg, st
        ret_dict = {}
        for bal_dict in j_ret:
            if bal_dict['type'] != 'exchange':
                continue

            if float(bal_dict['available']) > 0:
                if bal_dict['currency'] == 'qtm':
                    ret_dict['QTUM'] = float(bal_dict['available'])
                elif bal_dict['currency'] == 'dsh':
                    ret_dict['DASH'] = float(bal_dict['available'])
                else:
                    ret_dict[bal_dict['currency'].upper()] = float(bal_dict['available'])
        return success, ret_dict, '', 0

    async def get_trading_fee(self):
        success, val, msg, st = self.trading_api('account_infos')
        # self.last_retrieve_time = time.time()
        try:
            ret = float(val[0]['taker_fees'])/100.0
        except:
            return False, '', 'Bitfinex 거래수수료를 가져오는데 실패 하였습니다.', 3

        return True, ret, '', 0

    async def get_transaction_fee(self):
        success, j_ret, msg, st = self.trading_api('account_fees')
        if not success:
            return success, '', msg, st

        tx_fee = {key: Decimal(val) for key, val in j_ret['withdraw'].items()}

        if 'QTM' in tx_fee:
            tx_fee['QTUM'] = tx_fee.pop('QTM')
        if 'DSH' in tx_fee:
            tx_fee['DASH'] = tx_fee.pop('DSH')

        self._tx_fee.update(tx_fee)
        # last_retrieve_time = time.time()

        return success, self._tx_fee, msg, st

    def get_precision(self, pair):
        return True, (-8, -8), '', 0

    def buy(self, coin, amount, price="0.00000001"):
        symbol = coin.split('_')[1] + coin.split('_')[0]
        if symbol.lower() == 'qtumbtc':
            symbol = 'qtmbtc'
        elif symbol.lower() == 'dashbtc':
            symbol = 'dshbtc'
        extra_parameters = {'symbol': symbol,
                            'amount': '{0:.8f}'.format(amount),
                            'price': price,
                            'exchange': 'bitfinex',
                            'side': 'buy',
                            'type': 'exchange market'
                            }

        # if placing a limit type order
        if price != "0.00000001":
            extra_parameters['type'] = 'exchange limit'

        j_ret = self.trading_api('order/new', extra_parameters=extra_parameters)

        return j_ret

    def sell(self, coin, amount, price="0.00000001"):
        _from, _to = coin.split('_')
        symbol = _to + _from
        if symbol.lower() == 'qtumbtc':
            symbol = 'qtmbtc'
        elif symbol.lower() == 'dashbtc':
            symbol = 'dshbtc'
        extra_parameters = {'symbol': symbol,
                            'amount': '{0:.8f}'.format(amount),
                            'price': price,
                            'exchange': 'bitfinex',
                            'side': 'sell',
                            'type': 'exchange market'
                            }

        # if placing a limit type order
        if price != "0.00000001":
            extra_parameters['type'] = 'exchange limit'

        j_ret = self.trading_api('order/new', extra_parameters=extra_parameters)

        return j_ret

    def base_to_alt(self, currency, tradable_btc, alt_amount, td_fee, tx_fee):
        success, val, msg, st = self.buy(currency, alt_amount)
        if not success:
            return False, '', msg, st

        alt = alt_amount
        alt *= ((1 - Decimal(td_fee)) ** 1)
        alt -= Decimal(tx_fee[currency.split('_')[1]])
        alt = alt.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return True, alt, '', 0

    def alt_to_base(self, currency, tradable_btc, alt_amount):
        while True:
            success, val, msg, st = self.sell(currency, alt_amount)
            if success:
                break
            else:
                debugger.debug(msg)
                time.sleep(st)

    def get_order_status(self, order_id):
        extra_parameters = {'order_id': order_id}
        j_ret = self.trading_api('order/status', extra_parameters=extra_parameters)

        return j_ret

    def get_available_coin(self, currency='btc'):
        currency = currency.lower()
        if currency not in self.symbols:
            symbols = [(currency.upper() + '_' + symbol[:-3]).upper() for symbol in self.public_api('symbols') if
                       symbol.endswith(currency)]
            self.symbols[currency] = symbols

        return self.symbols[currency]

    async def get_deposit_addrs(self):
        available_coins = {
            'BTC': 'bitcoin',
            'LTC': 'litecoin',
            'ETH': 'ethereum',
            'ETC': 'ethereumc',
            'ZEC': 'zcash',
            'XMR': 'monero',
            'DASH': 'dash',
            'XRP': 'ripple',
            'EOS': 'eos',
            'QTUM': 'qtum',
            'BCH': 'bcash',
            'BTG': 'bgold',
            'OMG': 'omisego',
            'IOTA': 'iota',
        }
        ret_data = {}
        for key, val in available_coins.items():
            parameters = {
                "method": val,
                "wallet_name": "exchange",
            }

            success, j_ret, err_msg, err_slp = self.trading_api('deposit/new', extra_parameters=parameters)
            if not success:
                return False, '', err_msg, err_slp
            elif j_ret['result'] != 'success':
                return False, '', "Bitfinex[{}] 출금정보 조회 실패".format(val.upper()), 5

            if key == 'XRP':
                ret_data[key+'TAG'] = j_ret['address']
                ret_data[key] = j_ret['address_pool']
            elif key == 'EOS' or key == 'XMR':
                ret_data[key+'TAG'] = j_ret['address']
                ret_data[key] = j_ret['address_pool']
            else:
                ret_data[key] = j_ret['address']

        return True, ret_data, '', 0

    def cancel_order(self, order_id):
        self.trading_api('order/cancel', extra_parameters={'order_id': order_id})

    def cancel_multi(self, order_ids):
        self.trading_api('order/cancel/multi', extra_parameters={'orders': order_ids})

    def cancel_all(self):
        self.trading_api('order/cancel/all')

    def withdraw(self, coin, amount, to_address, payment_id=None):
        available_coins = {
            'BTC': 'bitcoin',
            'LTC': 'litecoin',
            'ETH': 'ethereum',
            'ETC': 'ethereumc',
            'ZEC': 'zcash',
            'XMR': 'monero',
            'DASH': 'dash',
            'XRP': 'ripple',
            'EOS': 'eos',
            'QTUM': 'qtum',
            'BCH': 'bcash',
            'BTG': 'bgold',
            'OMG': 'omisego',
            'IOTA': 'iota',
        }
        if coin not in available_coins:
            return False, '', "Bitfinex[{}] 자동이체 가능한 코인이 아닙니다.".format(coin.upper()), 0

        param = {
            'withdraw_type': available_coins[coin],
            'walletselected': 'exchange',
            'amount': '{0:8f}'.format(amount),
            'address': to_address
        }
        if payment_id is not None:
            param.update({
                'payment_id': payment_id
            })

        success, j_ret, msg, st = self.trading_api('withdraw', extra_parameters=param)
        if not success:
            return False, '', msg, st

        return True, j_ret, '', 0


    async def get_curr_avg_orderbook(self, currency_pairs, btc_sum=1):
        """
        :param currency_pairs:  list of strings in BTC_XXX form / ex) ['BTC_ETH', 'BTC_XRP']
        :param btc_sum: any positive number
        :return: average order book
        """
        currency_pairs = [''.join(cp.split('_')[::-1]).lower() for cp in currency_pairs]
        if 'qtumbtc' in currency_pairs:
            currency_pairs.remove('qtumbtc')
            currency_pairs.append('qtmbtc')
        if 'dashbtc' in currency_pairs:
            currency_pairs.remove('dashbtc')
            currency_pairs.append('dshbtc')
        if 'iotabtc' in currency_pairs:
            currency_pairs.remove('iotabtc')
            currency_pairs.append('iotbtc')

        avg_orderbook = {}
        loop = asyncio.get_event_loop()

        fts = {'BTC_' + pair[:-3].upper(): loop.run_in_executor(None, self.public_api, 'book', {'currencyPair': pair})
               for pair in currency_pairs}

        for pair, fut in fts.items():
            success, orderbook, msg, st = await fut
            if not success:
                return success, '', msg, st
            if pair == 'BTC_QTM':
                pair = 'BTC_QTUM'
            elif pair == 'BTC_DSH':
                pair = 'BTC_DASH'
            elif pair == 'BTC_IOT':
                pair = 'BTC_IOTA'

            avg_orderbook[pair] = {}
            for order_type in ['asks', 'bids']:
                sum = Decimal(0.0)
                total_coin_num = Decimal(0.0)
                for data in orderbook[order_type]:
                    price = data['price']
                    alt_coin_num = data['amount']
                    sum += Decimal(price) * Decimal(alt_coin_num)
                    total_coin_num += Decimal(alt_coin_num)
                    if sum > btc_sum:
                        break
                avg_orderbook[pair][order_type] = (sum/total_coin_num).quantize(Decimal(10) ** -8)

        return True, avg_orderbook, '', 0

    async def compare_orderbook(self, other, coins=[], default_btc=1):
        currency_pairs = coins
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            bitfinex_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs,
                                                                                              default_btc),
                                                                  other.get_curr_avg_orderbook(currency_pairs,
                                                                                               default_btc))
            success, bitfinex_avg_orderbook, err, st = bitfinex_result
            success2, other_avg_orderbook, err2, st2 = other_result
            if success and success2:
                m_to_s = {}
                for currency_pair in currency_pairs:
                    m_ask = bitfinex_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in currency_pairs:
                    m_bid = bitfinex_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                ret = (bitfinex_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m})

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