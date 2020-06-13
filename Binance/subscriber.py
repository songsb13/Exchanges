import websocket
try:
    import thread
except ImportError:
    import _thread as thread
import time

import json

from websocket import create_connection
from websocket import WebSocketConnectionClosedException

from Exchanges.custom_objects import DataStore
from Util.pyinstaller_patch import *


class BinanceSubscriber(threading.Thread):
    def __int__(self, data_store):
        super(BinanceSubscriber, self).__init__()
        self.data_store = data_store
        self.name = 'binance_subscriber'
        self.stop_flag = False

        self.websocket_app = websocket.WebSocketApp('wss://stream.binance.com:9443',
                                                    on_message=on_message,
                                                    on_error=on_error,
                                                    on_close=on_close,
                                                    on_open=on_open)
        
        # self.websocket_app.run_forever()

    def on_message(self, message):
        print(message)
    
    def on_error(self, error):
        print(error)
    
    def on_close(self):
        print("### closed ###")
    
    def on_open(self):
        def run(*args):
            class_obj, _ = args
            while not class_obj.stop_flag:
                class_obj.receiver()

        thread.start_new_thread(run, (self,))

    def receiver(self):
        pass
    

class BitfinexPublicSubscriber(threading.Thread):
    def __init__(self, data_store):
        super(BitfinexPublicSubscriber, self).__init__()
        self.data_store = data_store
        self.name = 'bitfinex_private_subscriber'
        self.public_stop_flag = False
        
        self._public_ws = create_connection('wss://api-pub.bitfinex.com/ws/2')
        self._temp_candle_store = dict()
        
        self._temp_orderbook_store = dict()
        
        self.orderbook_symbol_set = list()
        self.candle_symbol_set = list()
    
    def unsubscribe(self, chan_id):
        data = {"event": "unsubscribe", "chanId": chan_id}
        
        self._send_with_symbol_set(data, self.orderbook_symbol_set)
    
    def _send_with_symbol_set(self, data, symbol_set):
        """
            symbol_set: converted set BTC_XXX -> XXXBTC
        """
        for symbol in symbol_set:
            data = json.dumps(data) % symbol
            debugger.debug('send parameter [{}]'.format(data))
            
            self._public_ws.send(data)
    
    def subscribe_orderbook(self):
        data = {"freq": "F1", "len": "100", "event": "subscribe", "channel": "book",
                "symbol": 't%s'}
        
        self._send_with_symbol_set(data, self.orderbook_symbol_set)
    
    def subscribe_candle(self, time_):
        base_key = 'trade:{}'.format(time_)
        data = {"event": "subscribe", "channel": "candles", "key": base_key + ':t%s'}
        self._send_with_symbol_set(data, self.candle_symbol_set)
    
    def run(self):
        while not self.public_stop_flag:
            self.public_receiver()
    
    def public_receiver(self):
        try:
            message = self._public_ws.recv()
            message = json.loads(message)
            if 'event' in message:
                if 'channel' in message:
                    channel_id = message['chanId']
                    channel = message['channel']
                    if 'candle' in channel:
                        delimiter = message['key'].split(':t')[1]
                        point = self.data_store.candle_queue
                        self._temp_candle_store.update({delimiter: list()})
                    elif 'book' in channel:
                        delimiter = message['pair']
                        point = self.data_store.orderbook_queue
                        self._temp_orderbook_store.update({delimiter: list()})
                    
                    self.data_store.channel_set.update({channel_id: [channel, point, delimiter]})
            else:
                chan_id = message[0]
                channel, point, delimiter = self.data_store.channel_set[chan_id]
                if isinstance(message[1], list):
                    if 'candle' in channel:
                        if isinstance(message[1][0], list):
                            self._temp_candle_store[delimiter] += message[1]
                        else:
                            self._temp_candle_store[delimiter].append(message[1])
                        
                        if len(self._temp_candle_store[delimiter]) >= 200:
                            point[delimiter] = list()
                            point[delimiter] = self._temp_candle_store[delimiter]
                            self._temp_candle_store[delimiter] = list()
                    
                    elif 'book' in channel:
                        if isinstance(message[1][0], list):
                            # 처음에 값이 올 때 20개 이상의 list가 한꺼번에 옴.
                            self._temp_orderbook_store[delimiter] += message[1]
                        else:
                            self._temp_orderbook_store[delimiter].append(message[1])
                        
                        if len(self._temp_orderbook_store[delimiter]) >= 200:
                            point[delimiter] = list()
                            point[delimiter] = self._temp_orderbook_store[delimiter]
                            self._temp_orderbook_store[delimiter] = list()
        
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.public_stop_flag = True
            raise WebSocketConnectionClosedException
        
        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.public_stop_flag = True
            raise ex


def on_message(ws, message):
    print(message)

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("### closed ###")

def on_open(ws):
    def run(*args):
        for i in range(3):
            time.sleep(1)
            ws.send("Hello %d" % i)
        time.sleep(1)
        print("thread terminating...")
    thread.start_new_thread(run, ())


if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp("ws://echo.websocket.org/",
                              on_message = on_message,
                              on_error = on_error,
                              on_close = on_close)
    ws.on_open = on_open
    ws.run_forever()
