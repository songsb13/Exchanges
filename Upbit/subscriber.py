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
    orderbook_ticket = 10
    candle_ticket = 20



class UpbitSubscriber(threading.Thread):
    def __init__(self, data_store):
        super(UpbitSubscriber, self).__init__()
        self.data_tore = data_store
        self.name = 'upbit_subscriber'
        self.stop_flag = False
        self._upbit_websocket = create_connection('wss://api.upbit.com/websocket/v1')
    
    def _subscribes(self):
        data = [{"ticket": "gimo's_ticket"},
                {"type": "ticker", "codes": market_listing, "isOnlyRealtime": True}]

    def run(self):
        while not self.stop_flag:
            self.receiver()
        
    def stop(self):
        self.stop_flag = True
    
    def receiver(self):
        try:
            message = self.
        except
        

