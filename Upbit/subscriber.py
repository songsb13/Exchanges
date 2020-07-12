import json

import websocket
from websocket import create_connection
from websocket import WebSocketConnectionClosedException
from Util.pyinstaller_patch import *
from enum import Enum

class Tickets(Enum):
    """
        upbit는 개별 ticket값으로 구분함, 유니크 id로 구분
        1~1000: public
        1001~2000: private
    """
    ORDERBOOK = 10
    CANDLE = 20


class UpbitSubscriber2(websocket.WebSocketApp):
    def __init__(self, data_store, lock_dic):
        url = 'wss://api.upbit.com/websocket/v1'
        super(UpbitSubscriber2, self).__init__(url)
        self.data_store = data_store
        self.name = 'upbit_subscriber'
        self.stop_flag = False
        self._websocket, self._thread = self.start_websocket_thread()
        self._lock_dic = lock_dic
    
        self.candle_symbol_set = list()
        self.orderbook_symbol_set = list()
        self._temp_orderbook_store = list()
        self._temp_candle_store = list()
        
        self._subscribe_set = dict()
        
    def stop(self):
        self.stop_flag = True
    
    def start_websocket_thread(self):
        ws = websocket.WebSocketApp('wss://api.upbit.com/websocket/v1',
                                    on_message=self.on_message,
                                    on_close=self.on_close,
                                    )
    
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
    
        ws_thread.start()
        
        return ws, ws_thread

    def on_error(self, ws, error):
        pass

    def on_close(self, ws):
        pass
    
    def set_subscribe(self):
        data = list()
        for key, item in self._subscribe_set.items():
            data += self._subscribe_set[key]
        
        self.send(json.dumps(data))

    def unsubscribe_orderbook(self):
        self._subscribe_set.pop('orderbook')
        
        self.set_subscribe()

    def unsubscribe_candle(self):
        self._subscribe_set.pop('candle')

        self.set_subscribe()

    def subscribe_orderbook(self):
        self._subscribe_set['orderbook'] = [{"ticket": "{}".format(Tickets.ORDERBOOK.value)},
                                            {"type": 'orderbook', "codes": self.orderbook_symbol_set, "isOnlyRealtime": True}]
        
        self.set_subscribe()
    
    def subscribe_candle(self):
        self._subscribe_set['candle'] = [{"ticket": "{}".format(Tickets.CANDLE.value)},
                                         {"type": 'ticker', "codes": self.candle_symbol_set}]

        self.set_subscribe()

    def on_message(self, ws, message):
        try:
            data = json.loads(message.decode())
            market = data['code']
            type_ = data['type']
        
            if type_ == 'orderbook':
                with self._lock_dic['orderbook']:
                    self._temp_orderbook_store += data['orderbook_units']
                
                    if len(self._temp_orderbook_store) >= 100:
                        self.data_store.orderbook_queue[market] = self._temp_orderbook_store
                        self._temp_orderbook_store = list()
                    else:
                        self._temp_orderbook_store += data['orderbook_units']
        
            elif type_ == 'ticker':
                with self._lock_dic['candle']:
                    candle = dict(
                        timestamp=data['trade_timestamp'],
                        open=data['opening_price'],
                        close=data['trade_price'],
                        high=data['high_price'],
                        low=data['low_price']
                    )
                
                    self.data_store.candle_queue[market] = candle
        
            time.sleep(1)
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop_flag = True
            raise WebSocketConnectionClosedException
    
        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop_flag = True
            raise ex

