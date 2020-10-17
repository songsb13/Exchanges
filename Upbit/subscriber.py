import json

import websocket
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


class UpbitSubscriber(websocket.WebSocketApp):
    def __init__(self, data_store, lock_dic):
        debugger.debug('UpbitSubscriber init!')

        url = 'wss://api.upbit.com/websocket/v1'
        super(UpbitSubscriber, self).__init__(url,
                                              on_open=self.on_open,
                                              on_message=self.on_message,
                                              on_error=self.on_error,
                                              on_close=self.on_close)
        self.data_store = data_store
        self.name = 'upbit_subscriber'
        self.stop_flag = False
        self._lock_dic = lock_dic
    
        self.candle_symbol_set = list()
        self.orderbook_symbol_set = list()
        self._temp_orderbook_store = list()
        self._temp_candle_store = list()
        
        self.subscribe_set = dict()
        self.subscribe_thread = threading.Thread(target=self.run_forever, daemon=True)
        self.subscribe_thread.start()
        
        debugger.debug('UpbitSubscriber start!')
        
    def stop(self):
        self.stop_flag = True
    
    def on_error(self, ws, error):
        pass

    def on_close(self, ws):
        pass
    
    def on_open(self, ws):
        while True:
            time.sleep(0.1)
    
    def set_subscribe(self):
        data = list()
        for key, item in self.subscribe_set.items():
            data += self.subscribe_set[key]
        
        self.send(json.dumps(data))

    def unsubscribe_orderbook(self):
        self.subscribe_set.pop('orderbook')
        
        self.set_subscribe()

    def unsubscribe_candle(self):
        self.subscribe_set.pop('candle')

        self.set_subscribe()

    def subscribe_orderbook(self):
        self.subscribe_set['orderbook'] = [{"ticket": "{}".format(Tickets.ORDERBOOK.value)},
                                           {"type": 'orderbook', "codes": self.orderbook_symbol_set, "isOnlyRealtime": True}]
        
        self.set_subscribe()
    
    def subscribe_candle(self):
        self.subscribe_set['candle'] = [{"ticket": "{}".format(Tickets.CANDLE.value)},
                                        {"type": 'ticker', "codes": self.candle_symbol_set}]

        self.set_subscribe()

    def on_message(self, message):
        try:
            data = json.loads(message.decode())
            market = data['code']
            type_ = data['type']
            debugger.debug('get message [{}], [{}]'.format(market, type_))
            if type_ == 'orderbook':
                with self._lock_dic['orderbook']:
                    self._temp_orderbook_store += data['orderbook_units']
                
                    if len(self._temp_orderbook_store) >= 100:
                        self.data_store.orderbook_queue[market] = self._temp_orderbook_store
                        self._temp_orderbook_store = list()
                    else:
                        self._temp_orderbook_store += data['orderbook_units']
                    debugger.debug(self.data_store.orderbook_queue[market])
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
                    debugger.debug(self.data_store.candle_queue[market])
            time.sleep(1)
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop_flag = True
            raise WebSocketConnectionClosedException
    
        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop_flag = True
            raise ex

