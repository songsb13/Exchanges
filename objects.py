import websocket
import threading

from Util.pyinstaller_patch import debugger
from threading import Event
from Exchanges.settings import Consts

import decimal
import time
import asyncio
from decimal import Context

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
    def __init__(self, url, on_message):
        websocket.WebSocketApp.__init__(self, url, on_message=on_message)
        threading.Thread.__init__(self)

    def run(self) -> None:
        self.run_forever()


class BaseSubscriber(object):
    websocket_url = str()
    name = 'Base Subscriber'

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
            self.on_message
        )
        self._websocket_app.start()
        for _ in range(60):
            if self._websocket_app.keep_running:
                break
            time.sleep(0.5)

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
            self.data_store[symbol] = dict()

    def set_candle_symbol_set(self, symbol_list):
        self._candle_symbol_set = set(symbol_list)
        for symbol in symbol_list:
            self.data_store.candle_queue[symbol] = list()

    def set_subscribe_dict(self, list_):
        self._subscribe_dict = dict.fromkeys(list_, list())

    def stop(self):
        self._evt.clear()
