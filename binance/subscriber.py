try:
    import thread
except ImportError:
    import _thread as thread

import json
import websocket

from Util.pyinstaller_patch import *
from Exchanges.binance.setting import Urls


# class Receiver(threading.Thread):
#     def __init__(self, store_queue, params, _id, symbol_set, lock):
#         super(Receiver, self).__init__()
#         self.store_queue = store_queue
#         self._temp_queue = {symbol.upper(): list() for symbol in symbol_set}
#         self._params = params
#         self.lock = lock
#
#         path = Urls.Websocket.SINGLE if len(params) == 1 else Urls.Websocket.STREAMS
#         self._url = Urls.Websocket.BASE + path + '/'.join(params)
#
#         self._id = _id
#
#         self.stop_flag = False
#
#         self._symbol_set = symbol_set
#
#         self.websocket_app = create_connection(self._url)
#
#     def subscribe(self):
#         json_ = json.dumps({"method": "SUBSCRIBE", "params": self._params, 'id': self._id})
#
#         self.websocket_app.send(json_)
#
#     def unsubscribe(self, params=None):
#         if params is None:
#             # 차후 별개의 값들이 unsubscribe되어야 할 때
#             json_ = {"method": "UNSUBSCRIBE", "params": self._params, 'id': self._id}
#             self.websocket_app.send(json_)
#
#     def run(self):
#         while not self.stop_flag:
#             try:
#                 if self._id == Tickets.ORDERBOOK.value:
#                     self.orderbook_receiver()
#                 elif self._id == Tickets.CANDLE.value:
#                     self.candle_receiver()
#
#             except WebSocketConnectionClosedException:
#                 debugger.debug('Disconnected orderbook websocket.')
#                 self.stop()
#                 raise WebSocketConnectionClosedException
#
#             except Exception as ex:
#                 debugger.exception('Unexpected error from Websocket thread.')
#                 self.stop()
#                 raise ex
#
#     def stop(self):
#         self.websocket_app.close()
#         self.stop_flag = True
#

class BinanceSubscriber(websocket.WebSocketApp):
    def __init__(self, data_store, lock_dic):
        """
            data_store: An object for storing orderbook&candle data, using orderbook&candle queue in this object.
            lock_dic: dictionary for avoid race condition, {orderbook: Lock, candle: Lock}
        """
        debugger.debug('BinanceSubscriber::: start')
        
        url = 'wss://stream.binance.com:9443'
        super(BinanceSubscriber, self).__init__(url, on_message=self.on_message)
        
        self.data_store = data_store
        self.name = 'binance_subscriber'
        self.time = '1m'
        self._default_socket_id = 1
        self.stop_flag = False
        self._lock_dic = lock_dic
        
        self.symbol_set = set()
        self._temp_orderbook_store = dict()
        self._temp_candle_store = list()

    def add_candle_symbol_set(self, value):
        reset = False
        if isinstance(list, value):
            if not value.difference(set(self._candle_symbol_set)):
                self._candle_symbol_set = self._candle_symbol_set.union(set(value))
                reset = True
        elif isinstance(str, value):
            if value not in self._candle_symbol_set:
                self._candle_symbol_set.add(value)
                reset = True
    
        if reset is True:
            self.set_subscribe()

    def add_symbol_set(self, value):
        reset = False
        if isinstance(list, value):
            if not value.difference(set(self.symbol_set)):
                self.symbol_set = self.symbol_set.union(set(value))
                reset = True
        elif isinstance(str, value):
            if value not in self.symbol_set:
                self.symbol_set.add(value)
                reset = True
    
        if reset is True:
            self.set_subscribe()

    def stop(self):
        self.stop_flag = True

    def set_subscribe(self):
        set_to_list = list(self.symbol_set)
        data = json.dumps({"method": "SUBSCRIBE", "params": set_to_list, 'id': self._default_socket_id})
        self.send(data)

    def unsubscribe_orderbook(self):
        debugger.debug('BinanceSubscriber::: unsubscribe_orderbook')
        self.symbol_set.remove(Urls.Websocket.ALL_BOOK_TICKER)

        self.set_subscribe()

    def unsubscribe_candle(self, symbol):
        debugger.debug('BinanceSubscriber::: unsubscribe_candle')
        stream = Urls.Websocket.CANDLE.format(symbol=symbol, interval=self.time)
        self._candle_symbol_set.remove(stream)
        self.set_subscribe()

    def subscribe_orderbook(self):
        debugger.debug('BinanceSubscriber::: subscribe_orderbook')
        self.symbol_set.add(Urls.Websocket.ALL_BOOK_TICKER)
    
        self.set_subscribe()

    def subscribe_candle(self, symbol):
        debugger.debug('BinanceSubscriber::: subscribe_candle')
        stream = Urls.Websocket.CANDLE.format(symbol=symbol, interval=self.time)
        self._candle_symbol_set.add(stream)
        self.set_subscribe()

    def on_message(self, message):
        try:
            data = json.loads(message.decode())
            if 'result' not in data:
                if data in 'orderbook':
                    self.orderbook_receiver(data)
                else:
                    self.candle_receiver(data)
        except Exception as ex:
            print(ex)

    def orderbook_receiver(self, data):
        with self._lock_dic['orderbook']:
            data = data.get('data', None)
            symbol = data['s']
        
            self._temp_orderbook_store[symbol].append(dict(
                bids=dict(price=data['b'], amount=data['B']),
                asks=dict(price=data['a'], amount=data['A'])
            ))
        
            if len(self._temp_orderbook_store[symbol]) >= 20:
                self.data_store.orderbook_queue[symbol] = self._temp_orderbook_store[symbol]
                self._temp_orderbook_store[symbol] = list()

    def candle_receiver(self, data):
        with self._lock_dic['orderbook']:
            data = data.get('data', None)
            symbol = data['s']
            kline = data['k']
            self._temp_candle_store[symbol].append(dict(
                high=kline['h'],
                low=kline['l'],
                close=kline['c'],
                open=kline['o'],
                timestamp=kline['t'],
                volume=kline['v']
            ))
            if len(self._temp_orderbook_store[symbol]) >= 100:
                self.data_store.candle_queue[symbol] = self._temp_candle_store[symbol]
                self._temp_candle_store[symbol] = list()


