import json

from websocket import create_connection
from websocket import WebSocketConnectionClosedException
from Exchanges.base_exchange import DataStore
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
    def __init__(self, data_store):
        super(UpbitSubscriber, self).__init__()
        self.data_tore = data_store
        self.name = 'upbit_subscriber'
        self.stop_flag = False
        self._upbit_websocket = create_connection('wss://api.upbit.com/websocket/v1')
    
    def subscribe_orderbook(self, market_list):
        data = [{"ticket": Tickets.ORDERBOOK},
                {"type": 'orderbook', "codes": market_list, "isOnlyRealtime": True}]

        self._upbit_websocket.send(data)
        
    def subscribe_candle(self, market_list):
        data = [{"ticket": Tickets.CANDLE},
                {"type": 'trade', "codes": market_list, "isOnlyRealtime": True}]
        
        self._upbit_websocket.send(data)

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

        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop_flag = True
            raise WebSocketConnectionClosedException

        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop_flag = True
            raise ex
        

