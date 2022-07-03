import json

from websocket import WebSocketConnectionClosedException
from Util.pyinstaller_patch import *

from Exchanges.upbit.util import UpbitConverter as converter
from Exchanges.upbit.setting import Urls
from Exchanges.settings import Consts, Tickets
from Exchanges.objects import BaseSubscriber


class UpbitSubscriber(BaseSubscriber):
    websocket_url = Urls.Websocket.BASE
    name = 'Upbit Subscriber'

    def __init__(self, data_store, lock_dic):
        """
            data_store: An object for storing orderbook&candle data, using orderbook&candle queue in this object.
            lock_dic: dictionary for avoid race condition, {orderbook: Lock, candle: Lock}
        """
        debugger.debug(f'{self.name}::: start')

        super(UpbitSubscriber, self).__init__()

        self.data_store = data_store
        self._lock_dic = lock_dic

    def subscribe_orderbook(self):
        debugger.debug(f'{self.name}::: subscribe_orderbook')
        self._subscribe_dict[Consts.ORDERBOOK] = [
            {
                "ticket": Tickets.ORDERBOOK,
            },
            {
                "type": Consts.ORDERBOOK,
                "codes": list(self._orderbook_symbol_set),
                "isOnlyRealtime": True
            }
        ]
        self._send_with_subscribe_set()

    def subscribe_candle(self):
        debugger.debug(f'{self.name}::: subscribe_candle')
        self._subscribe_dict[Consts.CANDLE] = [
            {
                "ticket": Tickets.CANDLE,
            },
            {
                "type": Consts.TICKER,
                "codes": list(self._candle_symbol_set)
            }
        ]

        self._send_with_subscribe_set()

    def on_message(self, *args):
        obj_, message = args
        try:
            data = json.loads(message.decode())
            type_ = data['type']
            if type_ == Consts.ORDERBOOK:
                self.orderbook_receiver(data)
            elif type_ == Consts.TICKER:
                self.candle_receiver(data)
        except WebSocketConnectionClosedException:
            debugger.debug('Disconnected orderbook websocket.')
            self.stop()
            raise WebSocketConnectionClosedException
    
        except Exception as ex:
            debugger.exception('Unexpected error from Websocket thread.')
            self.stop()
            raise ex

    def orderbook_receiver(self, data):
        with self._lock_dic[Consts.ORDERBOOK]:
            symbol = data['code']
            sai_symbol = converter.exchange_to_sai(symbol)

            data_keys = {
                Consts.BID_PRICE_KEY: 'bid_price',
                Consts.BID_AMOUNT_KEY: 'bid_size',
                Consts.ASK_PRICE_KEY: 'ask_price',
                Consts.ASK_AMOUNT_KEY: 'ask_size'
            }

            total = self.temp_orderbook_setter(data['orderbook_units'], data_keys)
            self.data_store.orderbook_queue[sai_symbol] = total

    def candle_receiver(self, data):
        with self._lock_dic[Consts.CANDLE]:
            symbol = data['code']
            sai_symbol = converter.exchange_to_sai(symbol)
            candle_list = [
                data['opening_price'],
                data['high_price'],
                data['low_price'],
                data['trade_price'],
                data['trade_volume'],
                data['trade_timestamp'],
            ]

            store_list = self.temp_candle_setter(
                self.data_store.candle_queue[sai_symbol],
                candle_list
            )

            self.data_store.candle_queue[sai_symbol] = store_list

    def unsubscribe_orderbook(self, symbol):
        debugger.debug(f'{self.name}::: unsubscribe_orderbook')

        self._remove_contents(symbol, self._orderbook_symbol_set)

    def unsubscribe_candle(self, symbol):
        debugger.debug(f'{self.name}::: unsubscribe_candle')

        self._remove_contents(symbol, self._candle_symbol_set)

    def _remove_contents(self, symbol, symbol_set):
        try:
            symbol_set.remove(symbol)
        except Exception as ex:
            debugger.debug(f'{self.name}::: remove error, [{ex}]')

    def _send_with_subscribe_set(self):
        data = list()
        for key, item in self._subscribe_dict.items():
            data += self._subscribe_dict[key]

        self._websocket_app.send(str(data))


if __name__ == '__main__':
    from Exchanges.upbit.upbit import BaseUpbit

    _lock_dic = {
        Consts.ORDERBOOK: threading.Lock(),
        Consts.CANDLE: threading.Lock()
    }
    symbols = ["KRW_XRP", 'KRW_ETH']
    upbit = BaseUpbit('', '')
    upbit.set_subscriber()
    upbit.set_subscribe_orderbook(symbols)

    print('f')