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


class Receiver(threading.Thread):
    def __init__(self, data_store, params, _id):
        super(Receiver, self).__init__()
        self.data_store = data_store
        self._params = params
        self._url = 'wss://stream.binance.com:9443/ws/' + '/'.join(self._params)
        self._id = _id

        self._data = None
        self.stop_flag = False

        self._symbol_set = list()

        self.websocket_app = self.set_websocket_app()
        
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
        while not self.stop_flag:
            self.receiver()
    
    def stop(self):
        self.websocket_app.close()
        self.stop_flag = True
    
    def receiver(self):
        try:
            pass
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop()
            raise WebSocketConnectionClosedException

        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop()
            raise ex


class BinanceSubscriber(object):
    def __init__(self, data_store):
        super(BinanceSubscriber, self).__init__()
        self.data_store = data_store
        self.name = 'binance_subscriber'
        self.orderbook_symbol_set = list()
        self.candle_symbol_set = list()
        
        self.orderbook_receiver = None
        self.candle_receiver = None

    def unsubscribe_orderbook(self):
        if self.orderbook_receiver:
            self.orderbook_receiver.unsubscribe()
            self.orderbook_receiver.stop()

    def unsubscribe_candle(self):
        if self.candle_receiver:
            self.candle_receiver.unsubscribe()
            self.candle_receiver.stop()
    
    def subscribe_orderbook(self):
        if self.orderbook_symbol_set:
            params = ['{}@bookTicker'.format(symbol) for symbol in self.orderbook_symbol_set]
        else:
            # 전체 orderbook 가져옴.
            params = ['!bookTicker']
        
        self.orderbook_receiver = Receiver(
            self.data_store,
            params,
            ChannelIdSet.ORDERBOOK.value
        )
        self.orderbook_receiver.start()
            
    def subscribe_candle(self, time_):
        """
            time_: 1m, 3m, 5m, 15m, 30mm 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1m
        """
        params = ['{}@kline_{}'.format(symbol, time_) for symbol in self.candle_symbol_set]

        self.candle_receiver = Receiver(
            self.data_store,
            params,
            ChannelIdSet.CANDLE.value
        )
        self.candle_receiver.start()
