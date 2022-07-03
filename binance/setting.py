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
    GET_WITHDRAWAL_HISTORY = '/sapi/v1/capital/withdraw/history'
    GET_DEPOSIT_HISTORY = '/sapi/v1/capital/deposit/hisrec'
    GET_ALL_INFORMATION = '/sapi/v1/capital/config/getall'

    class Websocket(object):
        BASE = 'wss://stream.binance.com:9443/ws'
        SINGLE = '/ws'
        STREAMS = '/stream'

        SELECTED_BOOK_TICKER = '{symbol}@bookTicker'
        ALL_BOOK_TICKER = '!bookTicker'

        ORDERBOOK_DEPTH = '{symbol}@depth'
        
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


class WithdrawalStatus(object):
    EMAIL_SENT = 0
    CANCELLED = 1
    AWAITING_APPROVAL = 2
    REJECTED = 3
    PROCESSING = 4
    FAILURE = 5
    COMPLETED = 6


class FilterType(object):
    PRICE_FILTER = 'PRICE_FILTER'
    PERCENT_PRICE = 'PERCENT_PRICE'
    LOT_SIZE = 'LOT_SIZE'
    MIN_NOTIONAL = 'MIN_NOTIONAL'
    ICEBERG_PARTS = 'ICEBERG_PARTS'
    MARKET_LOT_SIZE = 'MARKET_LOT_SIZE'
    MAX_NUM_ORDERS = 'MAX_NUM_ORDERS'
    MAX_NUM_ALGO_ORDERS = 'MAX_NUM_ALGO_ORDERS'
