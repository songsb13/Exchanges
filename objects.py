import websocket

from Util.pyinstaller_patch import debugger
from threading import Event, Thread


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


class BaseSubscriber(websocket.WebSocketApp):
    def __init__(self, data_store, lock_dic):
        super(BaseSubscriber, self).__init__()

        self.data_store = data_store
        self._lock_dic = lock_dic

        self._evt = Event()
        self._evt.set()

        self._candle_symbol_set = set()
        self._orderbook_symbol_set = set()
        self._temp_orderbook_store = dict()
        self._temp_candle_store = dict()

        self.subscribe_set = dict()

    def is_running(self):
        return self.keep_running

    def set_orderbook_symbol_set(self, symbol_list):
        self._orderbook_symbol_set = symbol_list

    def set_candle_symbol_set(self, symbol_set):
        self._candle_symbol_set = symbol_set

    def start_run_forever_thread(self):
        debugger.debug('UpbitSubscriber::: start_run_forever_thread')
        self.subscribe_thread = Thread(target=self.run_forever, daemon=True)
        self.subscribe_thread.start()

    def stop(self):
        self._evt.clear()