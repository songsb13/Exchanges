import websocket
from websocket import WebSocketConnectionClosedException

from threading import Event
from decimal import Context

import time

import requests
import json
import threading
import aiohttp
import decimal

from Exchanges.messages import DebugMessage, WarningMessage
from Exchanges.settings import Consts

from Util.pyinstaller_patch import debugger

decimal.getcontext().prec = 8


class ExchangeResult(object):
    """
        Return exchange result abstract class

        success: True if success else False
        data: requested data if success is True else None
        message: result message if success is False else None
        wait_time: wait time for retry if success is False else 0
    """
    def __init__(self, success, data=None, message='', wait_time=0):

        self.success = success
        self.data = data
        self.message = message
        self.wait_time = wait_time


class DataStore(object):
    def __init__(self):
        self.channel_set = dict()
        self.activated_channels = list()
        self.orderbook_queue = dict()
        self.balance_queue = dict()
        self.candle_queue = dict()


class CustomWebsocket(websocket.WebSocketApp, threading.Thread):
    def __init__(self, url, on_message, ping_time_per_second):
        websocket.WebSocketApp.__init__(self, url, on_message=on_message)
        threading.Thread.__init__(self)
        self._ping_time_per_second = ping_time_per_second

    def run(self) -> None:
        self.run_forever(ping_interval=self._ping_time_per_second)


class BaseSubscriber(object):
    websocket_url = str()
    name = 'Base Subscriber'
    ping_time_per_second = 120

    def __init__(self):
        super(BaseSubscriber, self).__init__()

        self._evt = Event()
        self._evt.set()

        self._candle_symbol_set = set()
        self._orderbook_symbol_set = set()

        self._temp_candle_store = dict()

        self._subscribe_dict = dict()

        self._subscribe_thread = None
        self._websocket_app = None

        self.data_store = None

    def start_websocket_thread(self):
        self._websocket_app = CustomWebsocket(
            self.websocket_url,
            self.on_message,
            self.ping_time_per_second
        )
        self._websocket_app.start()
        for _ in range(60):
            time.sleep(0.5)
            if self._websocket_app.sock and self._websocket_app.keep_running:
                break

    def on_message(self, *args):
        return

    def temp_orderbook_setter(self, units, data_keys):
        total_bids, total_asks = [], []
        context = Context(prec=8)
        for each in units:
            bid_price = context.create_decimal(each[data_keys[Consts.BID_PRICE_KEY]])
            bid_amount = context.create_decimal(each[data_keys[Consts.BID_AMOUNT_KEY]])

            ask_price = context.create_decimal(each[data_keys[Consts.ASK_PRICE_KEY]])
            ask_amount = context.create_decimal(each[data_keys[Consts.ASK_AMOUNT_KEY]])

            total_bids.append([bid_price, bid_amount])
            total_asks.append([ask_price, ask_amount])
        dict_ = {
            Consts.BIDS: total_bids,
            Consts.ASKS: total_asks
        }
        return dict_

    def temp_candle_setter(self, store_list, candle_list):
        """
            Args:
                store_list: data_store.candle_queue[sai_symbol]
                candle_list: open, high, low, close, amount, timestamp
        """

        store_list.append(candle_list)
        if len(store_list) >= Consts.CANDLE_LIMITATION:
            store_list.pop(0)
        return store_list

    def subscribe_orderbook(self):
        pass

    def subscribe_candle(self):
        pass

    def set_orderbook_symbol_set(self, symbol_list):
        self._orderbook_symbol_set = set(symbol_list)
        for symbol in symbol_list:
            self.data_store.orderbook_queue[symbol] = dict()

    def set_candle_symbol_set(self, symbol_list):
        self._candle_symbol_set = set(symbol_list)
        for symbol in symbol_list:
            self.data_store.candle_queue[symbol] = list()

    def set_subscribe_dict(self, list_):
        self._subscribe_dict = dict.fromkeys(list_, list())

    def stop(self):
        self._evt.clear()


class BaseExchange(object):
    """
    all exchanges module should be followed BaseExchange format.
    """
    name = str()
    converter = None
    exchange_subscriber = None
    urls = None
    error_key = None

    def __init__(self):
        self._lock_dic = {
            Consts.ORDERBOOK: threading.Lock(),
            Consts.CANDLE: threading.Lock()
        }
        self.data_store = DataStore()

    def set_subscriber(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscriber", data=str(locals())))
        self._subscriber = self.exchange_subscriber(self.data_store, self._lock_dic)
        self._subscriber.start_websocket_thread()

    def set_subscribe_candle(self, sai_symbol_list):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_candle", data=str(locals())))

        exchange_symbols = list(map(self.converter.sai_to_exchange_subscriber, sai_symbol_list))
        self._subscriber.set_candle_symbol_set(exchange_symbols)
        self._subscriber.subscribe_candle()

    def set_subscribe_orderbook(self, sai_symbol_list):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_orderbook", data=str(locals())))

        exchange_symbols = list(map(self.converter.sai_to_exchange_subscriber, sai_symbol_list))
        self._subscriber.set_orderbook_symbol_set(exchange_symbols)
        self._subscriber.subscribe_orderbook()

    def get_orderbook(self):
        with self._lock_dic['orderbook']:
            debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_orderbook", data=str(locals())))
            orderbooks = self.data_store.orderbook_queue
            if not orderbooks:
                return ExchangeResult(False, message=WarningMessage.ORDERBOOK_NOT_STORED.format(name=self.name),
                                      wait_time=1)

            return ExchangeResult(True, orderbooks)

    def get_candle(self, sai_symbol):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_candle", data=str(locals())))
        with self._lock_dic['candle']:
            candles = self.data_store.candle_queue.get(sai_symbol, None)
            if candles is None:
                return ExchangeResult(False, message=WarningMessage.CANDLE_NOT_STORED.format(name=self.name),
                                      wait_time=1)
            return ExchangeResult(True, candles)

    async def get_curr_avg_orderbook(self, btc_sum=1.0):
        """
            {BTC_XRP: {bids: [[price, amount], ..], asks: [[price, amount], ..}
        """
        orderbook_result = self.get_orderbook()

        if not orderbook_result.success:
            return orderbook_result

        data_store_orderbook = orderbook_result.data
        average_orderbook = dict()
        for sai_symbol, orderbook_items in data_store_orderbook.items():
            exchange_symbol = self.converter.sai_to_exchange(sai_symbol)

            orderbooks = data_store_orderbook.get(exchange_symbol, None)
            if not orderbooks:
                continue

            average_orderbook[sai_symbol] = dict()

            for order_type in [Consts.ASKS, Consts.BIDS]:
                total_amount, total_price = decimal.Decimal(0), decimal.Decimal(0)
                for data in orderbook_items[order_type]:
                    price, amount = data

                    total_price += price * amount
                    total_amount += amount

                    if total_price > btc_sum:
                        break

                average_orderbook[sai_symbol][order_type] = (total_price / total_amount)
        if not average_orderbook:
            return ExchangeResult(
                success=False,
                message=''
            )
        else:
            return ExchangeResult(
                success=True,
                data=average_orderbook
            )

    def base_to_alt(self, alt_amount,
                    from_exchange_trading_fee,
                    to_exchange_transaction_fee):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="base_to_alt", data=str(locals())))
        alt_amount *= 1 - decimal.Decimal(from_exchange_trading_fee)
        alt_amount -= decimal.Decimal(to_exchange_transaction_fee)
        return alt_amount

    def fee_count(self):
        # BTC -> ALT(1), KRW -> BTC -> ALT(2)
        return 1

    def _get_result(self, response, path, extra, fn, error_key=error_key):
        try:
            if isinstance(response, requests.models.Response):
                result = response.json()
            else:
                result = json.loads(response)
        except:
            debugger.debug(DebugMessage.FATAL.format(name=self.name, fn=fn))
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

        if isinstance(result, dict):
            error = result.get(error_key, None)
        else:
            error = None

        if error is None:
            return ExchangeResult(
                success=True,
                data=result,
            )
        else:
            return ExchangeResult(
                success=False,
                message=error
            )

    def _public_api(self, path, extra):
        if extra is None:
            extra = dict()

        request = requests.get(self.urls.BASE + path, params=extra)
        return self._get_result(request, path, extra, fn='_public_api')

    async def _async_pubilc_api(self, path, extra=None):
        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession() as session:
            rq = await session.get(self.urls.BASE + path, params=extra)
            result_text = await rq.text()

            return self._get_result(result_text, path, extra, fn='_async_public_api')
