from enum import Enum


class Tickets(Enum):
    """
        1~1000: public
        1001~2000: private
    """

    ORDERBOOK = 10
    CANDLE = 20


class Urls(object):
    BASE = 'https://api.binance.com'
    PAGE_BASE = 'https://www.binance.com'

    EXCHANGE_INFO = '/api/v3/exchangeInfo'
    SERVER_TIME = '/api/v3/time'
    TICKER = '/api/v3/ticker/price'
    ORDER = '/api/v3/order'
    ACCOUNT = '/api/v3/account'
    ORDERBOOK = '/api/v3/depth'
    ALL_ORDERS = '/api/v3/allOrders'
    DEPOSITS = '/sapi/v1/capital/deposit/address'
    WITHDRAW = '/sapi/v1/capital/withdraw/apply'
    TRANSACTION_FEE = '/assetWithdraw/getAllAsset.html'

    class Websocket(object):
        BASE = 'wss://stream.binance.com:9443/ws'
        SINGLE = '/ws'
        STREAMS = '/stream'

        SELECTED_BOOK_TICKER = '{symbol}@bookTicker'
        ALL_BOOK_TICKER = '!bookTicker'
        
        CANDLE = '{symbol}@kline_{interval}'


class BinanceConsts(object):
    SUBSCRIBE = 'SUBSCRIBE'
    UNSUBSCRIBE = 'UNSUBSCRIBE'


class DepositStatus(object):
    PENDING = 0
    CREDITED_BUT_CANNOT_WITHDRAW = 6
    SUCCESS = 1


class OrderStatus(object):
    NEW = 'NEW'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'
    CANCELED = 'CANCELED'
    EXPIRED = 'EXPIRED'
