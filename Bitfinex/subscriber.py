import json

from websocket import create_connection
from websocket import WebSocketConnectionClosedException


from Exchanges.custom_objects import DataStore
from Util.pyinstaller_patch import *


class BitfinexSubscriber(threading.Thread):
    def __init__(self, data_store):
        super(BitfinexSubscriber, self).__init__()
        self.data_store = data_store
        self.temp_orderbook_store = dict()

        self.name = 'bitfinex_subscriber'

        self._private_ws = create_connection('wss://api.bitfinex.com/ws/2')
        self._public_ws = create_connection('wss://api-pub.bitfinex.com/ws/2')
        
        self.symbol_set = list()
        
    def run(self):
        if self.symbol_set:
            while True:
                self.public_receiver()
        else:
            debugger.info('You have to set symbol that using subscribe_orderbook.')
        
    def unsubscribe_orderbook(self):
        """
            symbol_set: converted set BTC_XXX -> XXXBTC
        """
        for symbol in self.symbol_set:
            data = {"freq": "F1", "len": "100", "event": "unsubscribe", "channel": "book", "symbol": 't' + symbol}
            data = json.dumps(data)
        
            debugger.debug('send parameter [{}]'.format(data))
            self._private_ws.send(data)

    def subscribe_orderbook(self):
        """
            symbol_set: converted set BTC_XXX -> XXXBTC
        """
        for symbol in self.symbol_set:
            data = {"freq": "F1", "len": "100", "event": "subscribe", "channel": "book", "symbol": 't' + symbol}
            data = json.dumps(data)
            
            debugger.debug('send parameter [{}]'.format(data))
            self._private_ws.send(data)
            
    def public_receiver(self):
        try:
            message = self._private_ws.recv()
            message = json.loads(message)
            if 'event' in message:
                if 'channel' in message:
                    pair = message['pair']
                    channel_id = message['chanId']
                    channel = message['channel']
                    
                    if 'book' in channel:
                        point = self.data_store.orderbook_queue
                        self.temp_orderbook_store.update({pair: list()})
                    self.data_store.channel_set.update({channel_id: [point, pair]})
            else:
                chan_id = message[0]
                point, pair = self.data_store.channel_set[chan_id]
                
                if isinstance(message[1][0], list):
                    # 처음에 값이 올 때 20개 이상의 list가 한꺼번에 옴.
                    self.temp_orderbook_store[pair] += message[1]
                else:
                    self.temp_orderbook_store[pair].append(message[1])
                
                if len(self.temp_orderbook_store[pair]) >= 200:
                    point[pair] = list()
                    point[pair] = self.temp_orderbook_store[pair]
                    self.temp_orderbook_store[pair] = list()

        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
        
        except:
            debugger.exception('Unexpected error from Websocket thread.')


if __name__ == '__main__':
    ds = DataStore()
    
    ss = BitfinexSubscriber(ds)
    
    setattr(ss, 'symbol_set', ['XRPBTC', 'ETHBTC'])
    
    ss.subscribe_orderbook()
    
    ss.public_receiver()