import json

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
        
        self.orderbook_subscribed = False
        self.candle_subscribed = False
    
    def subscribe_orderbook(self):
        data = [{"ticket": "{}".format(Tickets.ORDERBOOK.value)},
                {"type": 'orderbook', "codes": self.orderbook_symbol_set, "isOnlyRealtime": True}]
        
        self.orderbook_subscribed = True
        
        self._upbit_websocket.send(json.dumps(data))
        
    def subscribe_candle(self):
        data = [{"ticket": "{}".format(Tickets.CANDLE.value)},
                {"type": 'trade', "codes": self.candle_symbol_set, "isOnlyRealtime": True}]
        
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
            ticket = market['ticket']
            
            if ticket == Tickets.ORDERBOOK:
                with self._lock_dic['orderbook']:
                    self.data_store.orderbook_queue
                
            elif ticket == Tickets.CANDLE:
                with self._lock_dic['candle']:
                    self.data_store.candle_queue
            
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop_flag = True
            raise WebSocketConnectionClosedException

        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop_flag = True
            raise ex
        

