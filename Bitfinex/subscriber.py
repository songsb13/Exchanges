import json

from websocket import create_connection
from websocket import WebSocketConnectionClosedException


from Exchanges.custom_objects import DataStore
from Util.pyinstaller_patch import *


class BitfinexPublicSubscriber(threading.Thread):
    def __init__(self, data_store):
        super(BitfinexPublicSubscriber, self).__init__()
        self.data_store = data_store
        self.name = 'bitfinex_private_subscriber'
        self.public_stop_flag = False
        
        self._public_ws = create_connection('wss://api-pub.bitfinex.com/ws/2')
        
        self.symbol_set = list()
        
        self._temp_candle_store = dict()
        self._temp_orderbook_store = dict()

    def _send_with_symbol_set(self, data):
        """
            symbol_set: converted set BTC_XXX -> XXXBTC
        """
        for symbol in self.symbol_set:
            data = json.dumps(data.format(symbol))
            debugger.debug('send parameter [{}]'.format(data))

            self._public_ws.send(data)
        
    def subscribe_orderbook(self):
        data = {"freq": "F1", "len": "100", "event": "subscribe", "channel": "book",
                "symbol": 't{}'}
        
        self._send_with_symbol_set(data)
        
    def unsubscribe_orderbook(self):
        data = {"freq": "F1", "len": "100", "event": "unsubscribe", "channel": "book",
                "symbol": 't{}'}

        self._send_with_symbol_set(data)

    def subscribe_candle(self):
        data = {"event": "subscribe", "channel": "candle", "key": 't{}'}
        self._send_with_symbol_set(data)

    def unsubscribe_candle(self):
        data = {"event": "unsubscribe", "channel": "candle", "key": 't{}'}
        self._send_with_symbol_set(data)

    def run(self):
        while not self.public_stop_flag:
            if self.symbol_set:
                self.public_receiver()
    
    def public_receiver(self):
        try:
            message = self._public_ws.recv()
            message = json.loads(message)
            if 'event' in message:
                if 'channel' in message:
                    pair = message['pair']
                    channel_id = message['chanId']
                    channel = message['channel']
                    if 'candle' in channel:
                        point = self.data_store.candle_queue
                        self._temp_candle_store.update({pair: list()})
                    elif 'book' in channel:
                        point = self.data_store.orderbook_queue
                        self._temp_orderbook_store.update({pair: list()})

                    self.data_store.channel_set.update({channel_id: [channel, point, pair]})
            else:
                chan_id = message[0]
                channel, point, pair = self.data_store.channel_set[chan_id]
                
                if 'candle' in channel:
                    # todo orderbook 복사한 거라서 테스트 & 번경 필요할 수 있음.
                    if isinstance(message[1][0], list):
                        # 처음에 값이 올 때 20개 이상의 list가 한꺼번에 옴.
                        self._temp_candle_store[pair] += message[1]
                    else:
                        self._temp_candle_store[pair].append(message[1])
        
                    if len(self._temp_candle_store[pair]) >= 200:
                        point[pair] = list()
                        point[pair] = self._temp_candle_store[pair]
                        self._temp_candle_store[pair] = list()
                
                elif 'book' in channel:
                    if isinstance(message[1][0], list):
                        # 처음에 값이 올 때 20개 이상의 list가 한꺼번에 옴.
                        self._temp_orderbook_store[pair] += message[1]
                    else:
                        self._temp_orderbook_store[pair].append(message[1])
    
                    if len(self._temp_orderbook_store[pair]) >= 200:
                        point[pair] = list()
                        point[pair] = self._temp_orderbook_store[pair]
                        self._temp_orderbook_store[pair] = list()

        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.public_stop_flag = True
            raise WebSocketConnectionClosedException
    
        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.public_stop_flag = True
            raise ex
        

class BitfinexPrivateSubscriber(threading.Thread):
    def __init__(self, data_store):
        super(BitfinexPrivateSubscriber, self).__init__()
        self.data_store = data_store
        self.private_stop_flag = False

        self.name = 'bitfinex_public_subscriber'

        self._private_ws = create_connection('wss://api.bitfinex.com/ws/2')
        
        self.symbol_set = list()
        
    def run(self):
        if self.symbol_set:
            while not self.private_stop_flag:
                self.private_receiver()
        else:
            debugger.info('You have to set symbol that using subscribe_orderbook.')
        
    def private_receiver(self):
        pass
        # try:
        #     message = self._private_ws.recv()
        #     message = json.loads(message)
        #     if 'event' in message:
        #         if 'channel' in message:
        #             pair = message['pair']
        #             channel_id = message['chanId']
        #             channel = message['channel']
        #             if 'book' in channel:
        #                 point = self.data_store.orderbook_queue
        #                 self._temp_orderbook_store.update({pair: list()})
        #
        #             self.data_store.channel_set.update({channel_id: [channel, point, pair]})
        #     else:
        #         chan_id = message[0]
        #         channel, point, pair = self.data_store.channel_set[chan_id]
        #         if channel == 'orderbook':
        #             if isinstance(message[1][0], list):
        #                 # 처음에 값이 올 때 20개 이상의 list가 한꺼번에 옴.
        #                 self._temp_orderbook_store[pair] += message[1]
        #             else:
        #                 self._temp_orderbook_store[pair].append(message[1])
        #
        #             if len(self._temp_orderbook_store[pair]) >= 200:
        #                 point[pair] = list()
        #                 point[pair] = self._temp_orderbook_store[pair]
        #                 self._temp_orderbook_store[pair] = list()
        #
        # except WebSocketConnectionClosedException:
        #     debugger.debug('Disconnected orderbook websocket.')
        #     raise WebSocketConnectionClosedException
        # except Exception as ex:
        #     debugger.exception('Unexpected error from Websocket thread.')


if __name__ == '__main__':
    ds = DataStore()
    
    ss = BitfinexSubscriber(ds)
    
    setattr(ss, 'symbol_set', ['XRPBTC', 'ETHBTC'])
    
    ss.subscribe_orderbook()
    
    ss.public_receiver()
