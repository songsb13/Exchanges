try:
    import thread
except ImportError:
    import _thread as thread

import json
import decimal
from decimal import Context

from Exchanges.binance.util import BinanceConverter as converter
from Exchanges.binance.setting import Urls
from Exchanges.settings import Consts, Tickets
from Exchanges.objects import BaseSubscriber


decimal.getcontext().prec = 8


class BinanceSubscriber(BaseSubscriber):
    websocket_url = Urls.Websocket.BASE
    name = "Binance Subscriber"

    def __init__(self, data_store, lock_dic):
        """
        data_store: An object for storing orderbook&candle data, using orderbook&candle queue in this object.
        lock_dic: dictionary for avoid race condition, {orderbook: Lock, candle: Lock}
        """
        debugger.debug(f"{self.name}::: start")

        super(BinanceSubscriber, self).__init__()
        self.data_store = data_store
        self._interval = "1m"
        self._lock_dic = lock_dic

        self.subscribe_set = set()
        self.unsubscribe_set = set()

    def on_message(self, *args):
        obj_, message = args
        try:
            data = json.loads(message)
            if "error" in data:
                debugger.debug(
                    "BinanceSubscriber::: on_message error, not found messages [{}]".format(
                        data["error"]["msg"]
                    )
                )
                return
            if "result" not in data:
                # b: orderbook's price
                # B: orderbook's amount
                if "b" in data and "s" in data:
                    self.orderbook_receiver(data)
                else:
                    self.candle_receiver(data)
        except Exception as ex:
            debugger.debug("BinanceSubscriber::: on_message error, [{}]".format(ex))

    def orderbook_receiver(self, data):
        with self._lock_dic[Consts.ORDERBOOK]:
            symbol = data["s"]
            sai_symbol = converter.exchange_to_sai_subscriber(symbol)
            context = Context(prec=8)

            total_bids, total_asks = [], []
            for bid_price, bid_amount in data["b"]:
                total_bids.append(
                    [
                        context.create_decimal(bid_price),
                        context.create_decimal(bid_amount),
                    ]
                )

            for ask_price, ask_amount in data["a"]:
                total_asks.append(
                    [
                        context.create_decimal(ask_price),
                        context.create_decimal(ask_amount),
                    ]
                )

            self.data_store.orderbook_queue[sai_symbol] = {
                Consts.BIDS: total_bids,
                Consts.ASKS: total_asks,
            }

    def candle_receiver(self, data):
        with self._lock_dic[Consts.CANDLE]:
            kline = data["k"]
            symbol = kline["s"]
            sai_symbol = converter.exchange_to_sai_subscriber(symbol)
            candle_list = [
                kline["o"],
                kline["h"],
                kline["l"],
                kline["c"],
                kline["v"],
                kline["t"],
            ]
            store_list = self.temp_candle_setter(
                self.data_store.candle_queue[sai_symbol], candle_list
            )

            self.data_store.candle_queue[sai_symbol] = store_list

    def subscribe_orderbook(self):
        debugger.debug(f"{self.name}::: subscribe_orderbook")
        streams = [
            Urls.Websocket.ORDERBOOK_DEPTH.format(symbol=symbol)
            for symbol in self._orderbook_symbol_set
        ]
        self._subscribe_dict[Consts.ORDERBOOK] = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": Tickets.ORDERBOOK,
        }

        self._websocket_app.send(json.dumps(self._subscribe_dict[Consts.ORDERBOOK]))

    def subscribe_candle(self):
        debugger.debug(f"{self.name}::: subscribe_candle")
        streams = [
            Urls.Websocket.CANDLE.format(symbol=symbol, interval=self._interval)
            for symbol in self._candle_symbol_set
        ]
        self._subscribe_dict[Consts.CANDLE] = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": Tickets.CANDLE,
        }
        self._websocket_app.send(json.dumps(self._subscribe_dict[Consts.CANDLE]))
