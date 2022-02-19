"""
setting of whole exchanges
"""


class Consts(object):
    GET = 'GET'
    POST = 'POST'
    
    ASKS = 'asks'
    BIDS = 'bids'
    
    MARKET = 'market'
    LIMIT = 'limit'

    # Selling the BTC from primary, Selling the ALT from secondary
    PRIMARY_TO_SECONDARY = 'primary_to_secondary'

    # Selling the ALT from primary, Selling the BTc from secondary
    SECONDARY_TO_PRIMARY = 'secondary_to_primary'
    
    CANDLE_LIMITATION = 100
    ORDERBOOK_LIMITATION = 20
    
    CANDLE = 'candle'
    ORDERBOOK = 'orderbook'
    TICKER = 'ticker'

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
