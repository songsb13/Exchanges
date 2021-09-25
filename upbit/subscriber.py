import json

import websocket
from websocket import WebSocketConnectionClosedException
from Util.pyinstaller_patch import *
from enum import Enum
from Exchanges.upbit.setting import Urls
from Exchanges.settings import Consts

from threading import Event


class Tickets(Enum):
    """
        upbit는 개별 ticket값으로 구분함, 유니크 id로 구분
        1~1000: public
        1001~2000: private
    """
    ORDERBOOK = 10
    CANDLE = 20


class UpbitSubscriber(websocket.WebSocketApp):
    def __init__(self, data_store, lock_dic):
        """
            data_store: An object for storing orderbook&candle data, using orderbook&candle queue in this object.
            lock_dic: dictionary for avoid race condition, {orderbook: Lock, candle: Lock}
        """
        debugger.debug('UpbitSubscriber::: start')

        super(UpbitSubscriber, self).__init__(Urls.Websocket.BASE, on_message=self.on_message)
        
        self.data_store = data_store
        self.name = 'upbit_subscriber'
        self._lock_dic = lock_dic
    
        self._candle_symbol_set = set()
        self._orderbook_symbol_set = set()
        self._temp_orderbook_store = dict()
        self._temp_candle_store = dict()
        
        self.subscribe_set = dict()

        self.start_run_forever_thread()

    def _remove_contents(self, symbol, symbol_set):
        try:
            symbol_set.remove(symbol)
        except Exception as ex:
            debugger.debug('UpbitSubscriber::: remove error, [{}]'.format(ex))

    def _send_with_subscribe_set(self):
        data = list()
        for key, item in self.subscribe_set.items():
            data += self.subscribe_set[key]
    
        self.send(json.dumps(data))

    def start_run_forever_thread(self):
        debugger.debug('UpbitSubscriber::: start_run_forever_thread')
        self.subscribe_thread = threading.Thread(target=self.run_forever, daemon=True)
        self.subscribe_thread.start()

    def stop(self):
        self._evt = Event()
        self._evt.set()
    
    def subscribe_orderbook(self, values):
        debugger.debug('UpbitSubscriber::: subscribe_orderbook')
        if isinstance(values, (list, tuple, set)):
            self._orderbook_symbol_set = self._orderbook_symbol_set.union(set(values))

        if Consts.ORDERBOOK not in self.subscribe_set:
            self.subscribe_set.setdefault(Consts.ORDERBOOK, list())
        
        self.subscribe_set[Consts.ORDERBOOK] = [{"ticket": "{}".format(Tickets.ORDERBOOK.value)},
                                                     {"type": Consts.ORDERBOOK,
                                                      "codes": list(self._orderbook_symbol_set),
                                                      "isOnlyRealtime": True}]
    
        self._send_with_subscribe_set()

    def unsubscribe_orderbook(self, symbol):
        debugger.debug('UpbitSubscriber::: unsubscribe_orderbook')
        
        self._remove_contents(symbol, self._orderbook_symbol_set)
        self.subscribe_orderbook(symbol)

    def subscribe_candle(self, values):
        debugger.debug('UpbitSubscriber::: subscribe_candle')
        if isinstance(values, (list, tuple, set)):
            self._candle_symbol_set = self._candle_symbol_set.union(set(values))

        if Consts.CANDLE not in self.subscribe_set:
            self.subscribe_set.setdefault(Consts.CANDLE, list())

        self.subscribe_set[Consts.CANDLE] = [{"ticket": "{}".format(Tickets.CANDLE.value)},
                                                  {"type": Consts.TICKER, "codes": list(self._candle_symbol_set)}]

        self._send_with_subscribe_set()

    def unsubscribe_candle(self, symbol):
        debugger.debug('UpbitSubscriber::: unsubscribe_candle')
        
        self._remove_contents(symbol, self._candle_symbol_set)
        self.subscribe_candle(symbol)

    def on_message(self, *args):
        obj_, message = args
        try:
            data = json.loads(message.decode())
            type_ = data['type']
            if type_ == Consts.ORDERBOOK:
                self.orderbook_receiver(data)
            elif type_ == Consts.TICKER:
                self.candle_receiver(data)
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop()
            raise WebSocketConnectionClosedException
    
        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop()
            raise ex

    def orderbook_receiver(self, data):
        with self._lock_dic[Consts.ORDERBOOK]:
            market = data['code']
            # 1. insert data to temp_orderbook_store if type_ is 'orderbook'
            # 2. if more than 100 are filled, insert to orderbook_queue for using 'get_curr_avg_orderbook'
            if market not in self._temp_orderbook_store:
                self._temp_orderbook_store.setdefault(market, list())
        
            self._temp_orderbook_store[market] += data['orderbook_units']
        
            if len(self._temp_orderbook_store[market]) >= Consts.ORDERBOOK_LIMITATION:
                self.data_store.orderbook_queue[market] = self._temp_orderbook_store[market]
                self._temp_orderbook_store[market] = list()
    
    def candle_receiver(self, data):
        with self._lock_dic[Consts.CANDLE]:
            market = data['code']
            candle = dict(
                timestamp=data['trade_timestamp'],
                open=data['opening_price'],
                close=data['trade_price'],
                high=data['high_price'],
                low=data['low_price']
            )
            if market not in self._temp_candle_store:
                self._temp_candle_store.setdefault(market, list())
            self._temp_candle_store[market].append(candle)
            if len(self._temp_candle_store[market]) >= Consts.CANDLE_LIMITATION:
                self.data_store.candle_queue[market] = self._temp_candle_store[market]
                self._temp_candle_store[market] = list()
