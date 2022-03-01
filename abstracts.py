import requests
import json
import threading
import aiohttp

from decimal import Decimal, getcontext
from Exchanges.messages import DebugMessage, WarningMessage
from Exchanges.objects import ExchangeResult, DataStore
from Exchanges.settings import Consts

from Util.pyinstaller_patch import debugger


getcontext().prec = 8


class BaseExchange(object):
    """
    all exchanges module should be followed BaseExchange format.
    """
    name = str()
    sai_to_exchange_converter = None
    exchange_to_sai_converter = None
    exchange_subscriber = None
    urls = None

    def __init__(self):
        self._lock_dic = {
            Consts.ORDERBOOK: threading.Lock(),
            Consts.CANDLE: threading.Lock()
        }
        self.data_store = DataStore()

        self.set_subscriber()

    def set_subscriber(self):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscriber", data=str(locals())))
        self._subscriber = self.exchange_subscriber(self.data_store, self._lock_dic)
        self._subscriber.start_websocket_thread()

    def set_subscribe_candle(self, sai_symbol_list):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_candle", data=str(locals())))

        exchange_symbols = list(map(self.sai_to_exchange_converter, sai_symbol_list))
        self._subscriber.set_candle_symbol_set(exchange_symbols)

    def set_subscribe_orderbook(self, sai_symbol_list):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="set_subscribe_orderbook", data=str(locals())))

        exchange_symbols = list(map(self.sai_to_exchange_converter, sai_symbol_list))
        self._subscriber.set_orderbook_symbol_set(exchange_symbols)

    def get_orderbook(self):
        with self._lock_dic['orderbook']:
            debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_orderbook", data=str(locals())))
            with self._lock_dic['orderbook']:
                orderbooks = self.data_store.orderbook_queue
                if not orderbooks:
                    return ExchangeResult(False, message=WarningMessage.ORDERBOOK_NOT_STORED.format(name=self.name),
                                          wait_time=1)

                return ExchangeResult(True, orderbooks)

    def get_candle(self, sai_symbol):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="get_candle", data=str(locals())))
        with self._lock_dic['candle']:
            candles = self.data_store.candle_queue.get(sai_symbol, None)
            if candles is None:
                return ExchangeResult(False, message=WarningMessage.CANDLE_NOT_STORED.format(name=self.name),
                                      wait_time=1)
            return ExchangeResult(True, candles)

    def get_curr_avg_orderbook(self, btc_sum=1.0):
        """
            {BTC_XRP: {bids: [[price, amount], ..], asks: [[price, amount], ..}
        """
        orderbook_result = self.get_orderbook()

        if not orderbook_result.success:
            return orderbook_result

        data_store_orderbook = orderbook_result.data
        average_orderbook = dict()
        for sai_symbol, orderbook_items in data_store_orderbook.items():
            exchange_symbol = self.sai_to_exchange_converter(sai_symbol)

            orderbooks = data_store_orderbook.get(exchange_symbol, None)
            if not orderbooks:
                continue

            average_orderbook[sai_symbol] = dict()

            for order_type in [Consts.ASKS, Consts.BIDS]:
                total_amount, total_price = Decimal(0), Decimal(0)
                for data in orderbook_items[order_type]:
                    price, amount = data

                    total_price += price * amount
                    total_amount += amount

                    if total_price > btc_sum:
                        break

                average_orderbook[sai_symbol][order_type] = (total_price / total_amount)

            return ExchangeResult(
                success=True,
                data=average_orderbook
            )

    def base_to_alt(self, alt_amount,
                    from_exchange_trading_fee,
                    to_exchange_transaction_fee):
        debugger.debug(DebugMessage.ENTRANCE.format(name=self.name, fn="base_to_alt", data=str(locals())))
        alt_amount *= 1 - Decimal(from_exchange_trading_fee)
        alt_amount -= Decimal(to_exchange_transaction_fee)
        return alt_amount

    def fee_count(self):
        # BTC -> ALT(1), KRW -> BTC -> ALT(2)
        return 1

    def _get_result(self, response, path, extra, error_key, fn):
        try:
            if isinstance(response, requests.models.Response):
                result = response.json()
            else:
                result = json.loads(response)
        except:
            debugger.debug(DebugMessage.FATAL.format(name=self.name, fn=fn))
            return ExchangeResult(False, message=WarningMessage.EXCEPTION_RAISED.format(name=self.name), wait_time=1)

        if isinstance(result, dict):
            error = result.get(error_key, None)
        else:
            error = None

        if error is None:
            return ExchangeResult(
                success=True,
                data=result,
            )
        else:
            return ExchangeResult(
                success=False,
                message=error
            )

    def _public_api(self, path, extra, error_key):
        if extra is None:
            extra = dict()

        request = requests.get(self.urls.BASE + path, params=extra)
        return self._get_result(request, path, extra, error_key, fn='_public_api')

    async def _async_pubilc_api(self, path, extra=None):
        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession() as session:
            rq = await session.get(self.urls.BASE + path, params=extra)
            result_text = await rq.text()

            return self._get_result(result_text, path, extra, fn='_async_public_api')

