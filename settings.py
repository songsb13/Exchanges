"""
setting of whole exchanges
"""


class Tickets(object):
    """
        1~1000: public
        1001~2000: private
    """

    ORDERBOOK = 10
    CANDLE = 20


class Consts(object):
    GET = 'GET'
    POST = 'POST'
    
    ASKS = 'asks'
    BIDS = 'bids'
    
    MARKET = 'market'
    LIMIT = 'limit'
    CANDLE_LIMITATION = 100
    ORDERBOOK_LIMITATION = 20
    
    CANDLE = 'candle'
    ORDERBOOK = 'orderbook'
    TICKER = 'ticker'
    BALANCE = "balance"

    NOT_FOUND = 'not found'

    BID_PRICE_KEY = 'bid_price'
    ASK_PRICE_KEY = 'ask_price'

    BID_AMOUNT_KEY = 'bid_amount'
    ASK_AMOUNT_KEY = 'ask_amount'


class BaseMarkets(object):
    BTC = 'BTC'
    ETH = 'ETH'
    USDT = 'USDT'


class BaseTradeType(object):
    BUY_MARKET = 'BUY_MARKET'
    BUY_LIMIT = 'BUY_LIMIT'
    SELL_MARKET = 'SELL_MARKET'
    SELL_LIMIT = 'SELL_LIMIT'


class SaiOrderStatus(object):
    OPEN = 'open'
    ON_TRADING = 'on_trading'
    CLOSED = 'closed'
