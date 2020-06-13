import websocket
try:
    import thread
except ImportError:
    import _thread as thread

from enum import Enum

import json

from websocket import create_connection
from websocket import WebSocketConnectionClosedException

from Exchanges.custom_objects import DataStore
from Util.pyinstaller_patch import *


class ChannelIdSet(Enum):
    """
        Binance의 경우에는 channel Id를 정하는 형식이므로 임의로 정해서 보관한다.
        Public => 1~1000
        Private => 1001~ 2000
    """
    
    ORDERBOOK = 10
    CANDLE = 20


class BinanceSubscriber(threading.Thread):
    def __int__(self, data_store):
        super(BinanceSubscriber, self).__init__()
        self.data_store = data_store
        self.name = 'binance_subscriber'
        self.stop_flag = False
        self.orderbook_symbol_set = list()
        self.candle_symbol_set = list()

        self.websocket_app = websocket.WebSocketApp('wss://stream.binance.com:9443',
                                                    on_message=self.on_message,
                                                    on_error=self.on_error,
                                                    on_close=self.on_close,
                                                    on_open=self.on_open)
        
        # self.websocket_app.run_forever()

    def on_message(self, message):
        print(message)
    
    def on_error(self, error):
        print(error)
    
    def on_close(self):
        print("### closed ###")
    
    def on_open(self):
        while not self.stop_flag:
            self.receiver()
        
        # def run(*args):
        #     class_obj, _ = args
        #     while not class_obj.stop_flag:
        #         class_obj.receiver()
        #
        # thread.start_new_thread(run, (self,))

    def _send_data(self, data):
        """
            symbol_set: converted set BTC_XXX -> btcxxx
        """
        data = json.dumps(data)
        debugger.debug('send parameter [{}]'.format(data))
        self.websocket_app.send(data)
    
    def _unsubscribe(self, params, id_):
        data = {"method": "UNSUBSCRIBE", "params": params, 'id': id_}
        self._send_data(data)
    
    def unsubscribe_orderbook(self):
        params = ['{}@bookTicker'.format(symbol) for symbol in self.orderbook_symbol_set] \
            if self.orderbook_symbol_set else ['!bookTicker']

        self._unsubscribe(params, ChannelIdSet.ORDERBOOK.value)
        
    def unsubscribe_candle(self, time_):
        self._unsubscribe(['{}@kline_{}'.format(symbol, time_) for symbol in self.candle_symbol_set],
                          ChannelIdSet.CANDLE.value)
    
    def subscribe_orderbook(self):
        if self.orderbook_symbol_set:
            params = ['{}@bookTicker'.format(symbol) for symbol in self.orderbook_symbol_set]
        else:
            # 전체 orderbook 가져옴.
            params = ['!bookTicker']
        data = {"method": "SUBSCRIBE", "params": params}
        
        self._send_data(data)

    def subscribe_candle(self, time_):
        """
            time_: 1m, 3m, 5m, 15m, 30mm 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1m
        """
        params = ['{}@kline_{}'.format(symbol, time_) for symbol in self.candle_symbol_set]
        data = {"method": "SUBSCRIBE", "params": params}
    
        self._send_data(data)

    def receiver(self):
        pass
