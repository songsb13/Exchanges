import json

from websocket import create_connection
from Exchanges.custom_objects import DataStore
from Util.pyinstaller_patch import *


class BitfinexSubscriber(object):
    def __init__(self, data_store):
        self.data_store = data_store

        self.name = 'bitfinex_subscriber'

        self._private_ws = create_connection('wss://api.bitfinex.com/ws/2')
        self._public_ws = create_connection('wss://api-pub.bitfinex.com/ws/2')
    
    def unsubscribe_orderbook(self, symbol_set):
        """
            symbol_set: converted set BTC_XXX -> XXXBTC
        """
        for symbol in symbol_set:
            data = {"freq": "F1", "len": "100", "event": "unsubscribe", "channel": "book", "symbol": 't' + symbol}
            data = json.dumps(data)
        
            debugger.debug('send parameter [{}]'.format(data))
            self._private_ws.send(data)

    def subscribe_orderbook(self, symbol_set):
        """
            symbol_set: converted set BTC_XXX -> XXXBTC
        """
        for symbol in symbol_set:
            data = {"freq": "F1", "len": "100", "event": "subscribe", "channel": "book", "symbol": 't' + symbol}
            data = json.dumps(data)
            
            debugger.debug('send parameter [{}]'.format(data))
            self._private_ws.send(data)
            
    def public_receiver(self):
        """
            orderbook,
        """
        temp_orderbook_store = dict()
        while True:
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
                            temp_orderbook_store.update({pair: list()})
                        self.data_store.channel_set.update({channel_id: [point, pair]})
                else:
                    chan_id = message[0]
                    point, pair = self.data_store.channel_set[chan_id]
                    temp_orderbook_store[pair].append(message[1])
                    
                    if len(temp_orderbook_store[pair]) >= 20:
                        point.update({int(time.time()): temp_orderbook_store[pair]})
                        temp_orderbook_store[pair] = list()

            except Exception as ex:
                print(ex)
                debugger.debug('Disconnected Orderbook Websocket.')
                

if __name__ == '__main__':
    ds = DataStore()
    
    ss = BitfinexSubscriber(ds)
    
    ss.subscribe_orderbook(['XRPBTC', "ETHBTC"])
    
    ss.public_receiver()