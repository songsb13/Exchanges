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

# TODO Subscriber에 관한 문제점, recv가 block형태인데 같은 receiver에서 받아도 되는지에 대한 의문


class UpbitSubscriber2(object):
    def __init__(self):
        self._symbol_set = list()
        self.temp_store = list()
        
        self._websocket = self.start_websocket_thread()
        
        self._subscribe_set = dict()
        
    def start_websocket_thread(self):
        ws = websocket.WebSocketApp('wss://api.upbit.com/websocket/v1',
                                    on_message=self.on_message,
                                    on_close=self.on_close,
                                    )
    
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
    
        ws_thread.start()
        
        return ws

    def on_message(self, ws, message):
        pass

    def on_error(self, ws, error):
        pass

    def on_close(self, ws):
        pass
    
    def set_subscribe(self):
        data = list()
        for key, item in self._subscribe_set.items():
            data += self._subscribe_set[key]
    
        self._websocket.send(json.dumps(data))

    def unsubscribe_orderbook(self):
        self._subscribe_set.pop('orderbook')
        
        self.set_subscribe()

    def unsubscribe_candle(self):
        self._subscribe_set.pop('candle')

        self.set_subscribe()

    def subscribe_orderbook(self):
        self._subscribe_set['orderbook'] = [{"ticket": "{}".format(Tickets.ORDERBOOK.value)},
                                            {"type": 'orderbook', "codes": self._symbol_set, "isOnlyRealtime": True}]
        
        self.set_subscribe()
    
    def subscribe_candle(self):
        self._subscribe_set['candle'] = [{"ticket": "{}".format(Tickets.CANDLE.value)},
                                         {"type": 'ticker', "codes": self._symbol_set}]

        self.set_subscribe()


class UpbitSubscriber(threading.Thread):
    def __init__(self, data_store, lock_dic):
        super(UpbitSubscriber, self).__init__()
        self.data_store = data_store
        self.name = 'upbit_subscriber'
        self.stop_flag = False
        self._upbit_websocket = create_connection('wss://api.upbit.com/websocket/v1')
        self._lock_dic = lock_dic
        
        self.candle_symbol_set = list()
        self.orderbook_symbol_set = list()
        
        self._temp_orderbook_store = list()
        self._temp_candle_store = list()
        
        self.orderbook_subscribed = False
        self.candle_subscribed = False
        
        
        
    
    def subscribe_orderbook(self):
        data = [{"ticket": "{}".format(Tickets.ORDERBOOK.value)},
                {"type": 'orderbook', "codes": self.orderbook_symbol_set, "isOnlyRealtime": True}]
        
        self.orderbook_subscribed = True
        
        self._upbit_websocket.send(json.dumps(data))
        
    def subscribe_candle(self):
        data = [{"ticket": "{}".format(Tickets.CANDLE.value)},
                {"type": 'ticker', "codes": self.candle_symbol_set}]
        
        self.candle_subscribed = False
        self._upbit_websocket.send(json.dumps(data))

    def run(self):
        while not self.stop_flag:
            self.receiver()
        
    def stop(self):
        self.stop_flag = True
    
    def receiver(self):
        try:
            message = self._upbit_websocket.recv()
            
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
        

