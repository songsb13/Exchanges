import websocket
import threading

from Util.pyinstaller_patch import debugger
from threading import Event
from Exchanges.settings import Consts


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


class BaseSubscriber(object):
    websocket_url = str()
    name = 'Base Subscriber'

    def __init__(self):
        super(BaseSubscriber, self).__init__(self.websocket_url, on_message=self.on_message)

        self._evt = Event()
        self._evt.set()

        self._candle_symbol_set = set()
        self._orderbook_symbol_set = set()

        self._temp_candle_store = dict()

        self._subscribe_dict = dict()

        self._subscribe_thread = None

    def start_websocket_thread(self):
        debugger.debug('UpbitSubscriber::: start_run_forever_thread')
        websocket_app = websocket.WebSocketApp(
            self.websocket_url,
            on_message=self.on_message
        )

        self._subscribe_thread = threading.Thread(target=websocket_app.run_forever, daemon=True)
        self._subscribe_thread.start()

    def on_message(self, *args):
        return

    def temp_orderbook_setter(self, units, data_keys):
        total_bids, total_asks = [], []
        for each in units:
            bids = each[data_keys[Consts.BID_PRICE_KEY]], each[data_keys[Consts.BID_AMOUNT_KEY]]
            asks = each[data_keys[Consts.ASK_PRICE_KEY]], each[data_keys[Consts.ASK_AMOUNT_KEY]]

            total_bids.append(bids)
            total_asks.append(asks)
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

    def set_candle_symbol_set(self, symbol_list):
        self._candle_symbol_set = set(symbol_list)

    def set_subscribe_dict(self, list_):
        self._subscribe_dict = dict.fromkeys(list_, list())

    def stop(self):
        self._evt.clear()
