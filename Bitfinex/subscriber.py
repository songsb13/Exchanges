import json

from websocket import create_connection
from Util.pyinstaller_patch import *


class BitfinexSubscriber(object):
    def __init__(self, data_store):
        self.data_store = data_store

        self.name = 'bitfinex_subscriber'

        self._private_ws = create_connection('wss://api.bitfinex.com/ws/2')
        self._public_ws = create_connection('wss://api.bitfinex.com/ws/2')
    
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
        while True:
            try:
                message = self._private_ws.recv()
                print(message)
            
                if 'event' in message:
                    if 'channel' in message:
                        message = json.loads(message)
                        pair = message['pair']
                        channel_id = message['chanId']
                        channel = message['channel']
                        
                        if channel == 'orderbook':
                            queue_ = self.data_store.orderbook_queue
                        else:
                            'other queue..'
                            pass
                        
                        self.data_store.channel_set.update({{channel_id: [queue_, pair]}})
                        self.data_store.activated_channels.append(channel)

                else:
                    chan_id = message[0]
                    q, pair = self.data_store.channel_set[chan_id]
                    q[pair].put(message[1])
        
            except Exception as ex:
                print(ex)
                debugger.debug('Disconnected Websocket.')

    def public_receiver(self):
        """
            orderbook,
        """
        while True:
            try:
                message = self._private_ws.recv()
                print(message)
            
                if 'event' in message:
                    if 'channel' in message:
                        message = json.loads(message)
                        pair = message['pair']
                        channel_id = message['chanId']
                        channel = message['channel']
                    
                        if channel == 'orderbook':
                            queue_ = self.data_store.orderbook_queue
                        self.data_store.channel_set.update({{channel_id: [queue_, pair]}})
                else:
                    chan_id = message[0]
                    q, pair = self.data_store.channel_set[chan_id]
                    q[pair].put(message[1])
        
            except Exception as ex:
                print(ex)
                debugger.debug('Disconnected Orderbook Websocket.')

