class Websocket(object):
    BASE = "wss://stream.binance.com:9443/ws"
    SINGLE = "/ws"
    STREAMS = "/stream"

    SELECTED_BOOK_TICKER = "{symbol}@bookTicker"
    ALL_BOOK_TICKER = "!bookTicker"

    ORDERBOOK_DEPTH = "{symbol}@depth"

    CANDLE = "{symbol}@kline_{interval}"


class BinanceConsts(object):
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"


class DepositStatus(object):
    PENDING = 0
    CREDITED_BUT_CANNOT_WITHDRAW = 6
    SUCCESS = 1


class OrderStatus(object):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class WithdrawalStatus(object):
    EMAIL_SENT = 0
    CANCELLED = 1
    AWAITING_APPROVAL = 2
    REJECTED = 3
    PROCESSING = 4
    FAILURE = 5
    COMPLETED = 6


class FilterType(object):
    PRICE_FILTER = "PRICE_FILTER"
    PERCENT_PRICE = "PERCENT_PRICE"
    LOT_SIZE = "LOT_SIZE"
    MIN_NOTIONAL = "MIN_NOTIONAL"
    ICEBERG_PARTS = "ICEBERG_PARTS"
    MARKET_LOT_SIZE = "MARKET_LOT_SIZE"
    MAX_NUM_ORDERS = "MAX_NUM_ORDERS"
    MAX_NUM_ALGO_ORDERS = "MAX_NUM_ALGO_ORDERS"
