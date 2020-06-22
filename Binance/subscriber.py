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
from copy import deepcopy


class ChannelIdSet(Enum):
    """
        Binance의 경우에는 channel Id를 정하는 형식이므로 임의로 정해서 보관한다.
        Public => 1~1000
        Private => 1001~ 2000
    """
    
    ORDERBOOK = 10
    CANDLE = 20


class Receiver(threading.Thread):
    def __init__(self, store_queue, params, _id, symbol_set):
        super(Receiver, self).__init__()
        self.store_queue = store_queue
        self._temp_queue = {symbol.upper(): list() for symbol in symbol_set}
        self._params = params
        self._url = 'wss://stream.binance.com:9443'

        if len(params) == 1:
            self._url += '/ws' + '/'.join(params)
        elif len(params) >= 2:
            self._url += '/stream?streams=' + '/'.join(params)
            
        self._id = _id

        self.stop_flag = False

        self._symbol_set = symbol_set

        self.websocket_app = create_connection(self._url)
    
    def subscribe(self):
        json_ = json.dumps({"method": "SUBSCRIBE", "params": self._params, 'id': self._id})
        
        self.websocket_app.send(json_)
    
    def unsubscribe(self, params=None):
        if params is None:
            # 차후 별개의 값들이 unsubscribe되어야 할 때
            json_ = {"method": "UNSUBSCRIBE", "params": self._params, 'id': self._id}
            self.websocket_app.send(json_)

    # def set_websocket_app(self):
    #     return websocket.WebSocketApp(
    #         url=self._url,
    #         on_message=self.on_message,
    #         on_error=self.on_error,
    #         on_close=self.on_close,
    #     )
    def run(self):
        while not self.stop_flag:
            try:
                if self._id == ChannelIdSet.ORDERBOOK.value:
                    self.orderbook_receiver()
                elif self._id == ChannelIdSet.CANDLE.value:
                    self.candle_receiver()
                    
            except WebSocketConnectionClosedException:
                debugger.debug('Disconnected orderbook websocket.')
                self.stop()
                raise WebSocketConnectionClosedException

            except Exception as ex:
                debugger.exception('Unexpected error from Websocket thread.')
                self.stop()
                raise ex

    def stop(self):
        self.websocket_app.close()
        self.stop_flag = True
    
    def orderbook_receiver(self):
        message = json.loads(self.websocket_app.recv())
        if 'result' not in message:
            data = message.get('data', None)
            symbol = data['s']
            
            self._temp_queue[symbol].append(dict(
                bids=dict(price=data['b'], amount=data['B']),
                asks=dict(price=data['a'], amount=data['A'])
            ))
            
            if len(self._temp_queue[symbol]) >= 20:
                self.store_queue[symbol] = deepcopy(self._temp_queue[symbol])
                self._temp_queue[symbol] = list()
                
    def candle_receiver(self):
        message = json.loads(self.websocket_app.recv())
        if 'result' not in message:
            data = message.get('data', None)
            symbol = data['s']
            kline = data['k']
            self._temp_queue[symbol].append(dict(
                high=kline['h'],
                low=kline['l'],
                close=kline['c'],
                open=kline['o'],
                timestamp=kline['t'],
                volume=kline['v']
            ))
        
            if len(self._temp_queue[symbol]) >= 20:
                self.store_queue[symbol] = deepcopy(self._temp_queue[symbol])
                self._temp_queue[symbol] = list()


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
            self.data_store.orderbook_queue,
            params,
            ChannelIdSet.ORDERBOOK.value,
            self.orderbook_symbol_set
        )
        self.orderbook_receiver.subscribe()
        self.orderbook_receiver.start()
            
    def subscribe_candle(self, time_):
        """
            time_: 1m, 3m, 5m, 15m, 30m 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        """
        params = ['{}@kline_{}'.format(symbol, time_) for symbol in self.candle_symbol_set]
        self.candle_receiver = Receiver(
            self.data_store.candle_queue,
            params,
            ChannelIdSet.CANDLE.value,
            self.candle_symbol_set
        )
        self.candle_receiver.subscribe()
        self.candle_receiver.start()
