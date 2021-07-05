try:
    import thread
except ImportError:
    import _thread as thread

import json
import websocket

from Util.pyinstaller_patch import *
from Exchanges.binance.setting import Urls
from Exchanges.settings import Consts


class BinanceSubscriber(websocket.WebSocketApp):
    def __init__(self, data_store, lock_dic):
        """
            data_store: An object for storing orderbook&candle data, using orderbook&candle queue in this object.
            lock_dic: dictionary for avoid race condition, {orderbook: Lock, candle: Lock}
        """
        debugger.debug('BinanceSubscriber::: start')
        
        super(BinanceSubscriber, self).__init__(Urls.Websocket.BASE, on_message=self.on_message)
        
        websocket.enableTrace(True)
        self.data_store = data_store
        self.name = 'binance_subscriber'
        self.time = '30m'
        self._default_socket_id = 1
        self._unsub_id = 2
        self.stop_flag = False
        self._lock_dic = lock_dic
        
        self.subscribe_set = set()
        self.unsubscribe_set = set()
        self._temp_orderbook_store = dict()
        self._temp_candle_store = dict()

        self.start_run_forever_thread()

    def _switching_parameters(self, stream, is_subscribe=True):
        try:
            if is_subscribe:
                self.subscribe_set.add(stream)
                self.unsubscribe_set.remove(stream)
            else:
                self.subscribe_set.remove(stream)
                self.unsubscribe_set.add(stream)
        except Exception as ex:
            debugger.debug('BinanceSubscriber::: _switching_parameters error, [{}]'.format(ex))
        return

    def _subscribe(self):
        set_to_list = list(self.subscribe_set)
        data = json.dumps({"method": "SUBSCRIBE", "params": set_to_list, 'id': self._default_socket_id})
        self.send(data)

    def _unsubscribe(self):
        set_to_list = list(self.unsubscribe_set)
        data = json.dumps({"method": "UNSUBSCRIBE", "params": set_to_list, 'id': self._unsub_id})
        self.send(data)

    def start_run_forever_thread(self):
        debugger.debug('BinanceSubscriber::: start_run_forever_thread')
        self.subscribe_thread = threading.Thread(target=self.run_forever, daemon=True)
        self.subscribe_thread.start()

    def stop(self):
        self.stop_flag = True
    
    def subscribe_orderbook(self, value):
        debugger.debug('BinanceSubscriber::: subscribe_orderbook')
        if isinstance(value, list):
            for val in value:
                stream = Urls.Websocket.SELECTED_BOOK_TICKER.format(symbol=val)
                self._switching_parameters(stream, is_subscribe=True)
        elif isinstance(value, str):
            stream = Urls.Websocket.SELECTED_BOOK_TICKER.format(symbol=value)
            self._switching_parameters(stream, is_subscribe=True)

        self._subscribe()

    def unsubscribe_orderbook(self, symbol):
        debugger.debug('BinanceSubscriber::: unsubscribe_orderbook')
        stream = Urls.Websocket.SELECTED_BOOK_TICKER.format(symbol=symbol)
        self._switching_parameters(stream, is_subscribe=False)

        self._unsubscribe()

    def subscribe_candle(self, value):
        debugger.debug('BinanceSubscriber::: subscribe_candle')
        if isinstance(value, list):
            for val in value:
                stream = Urls.Websocket.CANDLE.format(symbol=val, interval=self.time)
                self._switching_parameters(stream, is_subscribe=True)
        elif isinstance(value, str):
            stream = Urls.Websocket.CANDLE.format(symbol=value, interval=self.time)
            self._switching_parameters(stream, is_subscribe=True)

        self._subscribe()

    def unsubscribe_candle(self, symbol):
        debugger.debug('BinanceSubscriber::: unsubscribe_candle')
        stream = Urls.Websocket.CANDLE.format(symbol=symbol, interval=self.time)
        self._switching_parameters(stream, is_subscribe=False)
        
        self._unsubscribe()

    def on_message(self, *args):
        obj_, message = args
        try:
            data = json.loads(message)
            if 'result' not in data:
                if 'b' in data and 'B' in data:
                    self.orderbook_receiver(data)
                else:
                    self.candle_receiver(data)
        except Exception as ex:
            debugger.debug('BinanceSubscriber::: on_message error, [{}]'.format(ex))

    def orderbook_receiver(self, data):
        with self._lock_dic['orderbook']:
            symbol = data['s']
            self._temp_orderbook_store.setdefault(symbol, list())
        
            self._temp_orderbook_store[symbol].append(dict(
                bids=dict(price=data['b'], amount=data['B']),
                asks=dict(price=data['a'], amount=data['A'])
            ))
        
            if len(self._temp_orderbook_store[symbol]) >= Consts.ORDERBOOK_LIMITATION:
                self.data_store.orderbook_queue[symbol] = self._temp_orderbook_store[symbol]
                self._temp_orderbook_store[symbol] = list()

    def candle_receiver(self, data):
        with self._lock_dic['orderbook']:
            kline = data['k']
            symbol = kline['s']
            self._temp_candle_store.setdefault(symbol, list())
            self._temp_candle_store[symbol].append(dict(
                high=kline['h'],
                low=kline['l'],
                close=kline['c'],
                open=kline['o'],
                timestamp=kline['t'],
                volume=kline['v']
            ))
            if len(self._temp_candle_store[symbol]) >= Consts.CANDLE_LIMITATION:
                self.data_store.candle_queue[symbol] = self._temp_candle_store[symbol]
                self._temp_candle_store[symbol] = list()
