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
        """
            data_store: An object for storing orderbook&candle data, using orderbook&candle queue in this object.
            lock_dic: dictionary for avoid race condition, {orderbook: Lock, candle: Lock}
        """
        debugger.debug('UpbitSubscriber::: start')

        url = 'wss://api.upbit.com/websocket/v1'
        super(UpbitSubscriber, self).__init__(url, on_message=self.on_message)
        
        self.data_store = data_store
        self.name = 'upbit_subscriber'
        self.stop_flag = False
        self._lock_dic = lock_dic
    
        self._candle_symbol_set = list()
        self._orderbook_symbol_set = list()
        self._temp_orderbook_store = dict()
        self._temp_candle_store = list()
        
        self.subscribe_set = dict()
    
    def add_candle_symbol_set(self, value):
        reset = False
        if isinstance(list, value):
            if not value.difference(set(self._candle_symbol_set)):
                self._candle_symbol_set = self._candle_symbol_set.union(set(value))
                reset = True
        elif isinstance(str, value):
            if value not in self._candle_symbol_set:
                self._candle_symbol_set.add(value)
                reset = True
    
        if reset is True:
            self.unsubscribe_candle()
            self.subscribe_candle()

    def add_orderbook_symbol_set(self, value):
        reset = False
        if isinstance(list, value):
            if not value.difference(set(self._orderbook_symbol_set)):
                self._orderbook_symbol_set += value
                reset = True
        elif isinstance(str, value):
            if value not in self._orderbook_symbol_set:
                self._orderbook_symbol_set.append(value)
                reset = True
                
        if reset is True:
            self.unsubscribe_orderbook()
            self.subscribe_orderbook()
        
    def stop(self):
        self.stop_flag = True
    
    def set_subscribe(self):
        data = list()
        for key, item in self.subscribe_set.items():
            data += self.subscribe_set[key]
        
        self.send(json.dumps(data))

    def unsubscribe_orderbook(self):
        debugger.debug('UpbitSubscriber::: unsubscribe_orderbook')

        self.subscribe_set.pop('orderbook')
        
        self.set_subscribe()

    def unsubscribe_candle(self):
        debugger.debug('UpbitSubscriber::: unsubscribe_candle')
        self.subscribe_set.pop('candle')

        self.set_subscribe()

    def subscribe_orderbook(self):
        debugger.debug('UpbitSubscriber::: subscribe_orderbook')
        self.subscribe_set['orderbook'] = [{"ticket": "{}".format(Tickets.ORDERBOOK.value)},
                                           {"type": 'orderbook', "codes": self._orderbook_symbol_set, "isOnlyRealtime": True}]
        
        self.set_subscribe()
    
    def subscribe_candle(self):
        debugger.debug('UpbitSubscriber::: subscribe_candle')
        self.subscribe_set['candle'] = [{"ticket": "{}".format(Tickets.CANDLE.value)},
                                        {"type": 'ticker', "codes": self._candle_symbol_set}]

        self.set_subscribe()

    def on_message(self, message):
        try:
            data = json.loads(message.decode())
            market = data['code']
            type_ = data['type']
            debugger.debug('get message [{}], [{}]'.format(market, type_))
            if type_ == 'orderbook':
                with self._lock_dic['orderbook']:
                    # 1. insert data to temp_orderbook_store if type_ is 'orderbook'
                    # 2. if more than 100 are filled, insert to orderbook_queue for using 'get_curr_avg_orderbook'
                    if market not in self._temp_orderbook_store:
                        self._temp_orderbook_store.setdefault(market, list())
                        
                    self._temp_orderbook_store[market] += data['orderbook_units']

                    if len(self._temp_orderbook_store[market]) >= 100:
                        self.data_store.orderbook_queue[market] = self._temp_orderbook_store
                        self._temp_orderbook_store[market] = list()

                    debugger.debug(self.data_store.orderbook_queue.get(market, None))
            elif type_ == 'ticker':
                with self._lock_dic['candle']:
                    candle = dict(
                        timestamp=data['trade_timestamp'],
                        open=data['opening_price'],
                        close=data['trade_price'],
                        high=data['high_price'],
                        low=data['low_price']
                    )
                    self._temp_candle_store[market].append(candle)
                    if len(self._temp_orderbook_store[market]) >= 100:
                        self.data_store.candle_queue[market] = self._temp_candle_store[market]
                        self._temp_candle_store[market] = list()
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop_flag = True
            raise WebSocketConnectionClosedException
    
        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop_flag = True
            raise ex

