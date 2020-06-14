import websocket
try:
    import thread
except ImportError:
    import _thread as thread

from enum import Enum

import json

from Util.pyinstaller_patch import *
from websocket import create_connection
from websocket import WebSocketConnectionClosedException


class ChannelIdSet(Enum):
    """
        Binance의 경우에는 channel Id를 정하는 형식이므로 임의로 정해서 보관한다.
        Public => 1~1000
        Private => 1001~ 2000
    """
    
    ORDERBOOK = 10
    CANDLE = 20


class Receiver(object):
    def __init__(self, data_store, params, _id):
        super(Receiver, self).__init__()
        self.data_store = data_store
        self.websocket_app = self.set_websocket_app()
        self._symbol_set = list()
        
        self._params = params
        self._id = _id
        
        self._url = 'wss://stream.binance.com:9443/ws/' + '/'.join(self._params)
        self._data = None
        self.stop_flag = False
    
    def subscribe(self):
        self._data = {"method": "SUBSCRIBE", "params": self._params}
    
    def unsubscribe(self, params=None):
        if params is None:
            # 차후 별개의 값들이 unsubscribe되어야 할 때
            self._data = {"method": "UNSUBSCRIBE", "params": self._params, 'id': self._id}
        
    def set_websocket_app(self):
        return websocket.WebSocketApp(
            url=self._url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
    
    def on_message(self, message):
        print(message)

    def on_error(self, error):
        print(error)

    def on_close(self):
        print("### closed ###")

    def on_open(self):
        def run(*args):
            class_obj, *_ = args
            while not self.stop_flag:
                class_obj.receiver()
    
        if not self.stop_flag:
            thread.start_new_thread(run, (self,))
    
    def receiver(self):
        try:
            pass
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop_flag = True
            raise WebSocketConnectionClosedException

        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop_flag = True
            raise ex


class BinanceSubscriber():
    def __init__(self, data_store):
        super(BinanceSubscriber, self).__init__()
        self.data_store = data_store
        self.name = 'binance_subscriber'
        self.orderbook_symbol_set = list()
        self.candle_symbol_set = list()
        
        self._orderbook_receiver = None
        self._candle_receiver = None

    def unsubscribe_orderbook(self):
        if self._orderbook_receiver:
            self._orderbook_receiver.unsubscribe()
            self._orderbook_receiver.websocket_app.close()

    def unsubscribe_candle(self):
        if self._orderbook_receiver:
            self._orderbook_receiver.unsubscribe()
            self._orderbook_receiver.websocket_app.close()
    
    def subscribe_orderbook(self):
        if self.orderbook_symbol_set:
            params = ['{}@bookTicker'.format(symbol) for symbol in self.orderbook_symbol_set]
        else:
            # 전체 orderbook 가져옴.
            params = ['!bookTicker']
        
        if self._orderbook_receiver is None:
            self._orderbook_receiver = Receiver(
                self.data_store,
                params,
                ChannelIdSet.ORDERBOOK.value
            )
            self._orderbook_receiver.websocket_app.run_forever()
            
    def subscribe_candle(self, time_):
        """
            time_: 1m, 3m, 5m, 15m, 30mm 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1m
        """
        params = ['{}@kline_{}'.format(symbol, time_) for symbol in self.candle_symbol_set]

        if self._candle_receiver is None:
            self._candle_receiver = Receiver(
                self.data_store,
                params,
                ChannelIdSet.CANDLE.value
            )
            self._candle_receiver.websocket_app.run_forever()

