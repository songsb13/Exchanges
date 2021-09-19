from enum import Enum


class Tickets(Enum):
    """
        1~1000: public
        1001~2000: private
    """
    ORDERBOOK = 10
    CANDLE = 20


class Urls(object):
    BASE = 'https://api.upbit.com/v1'
    TICKER = '/ticker'
    ORDER = '/order'
    CURRENCY = '/market/all'
    WITHDRAW = '/withdraws/coin'
    ACCOUNT = '/accounts'
    ORDERBOOK = '/orderbook'
    DEPOSIT_ADDRESS = '/v1/deposits/coin_addresses'
    
    class Websocket(object):
        BASE = 'wss://api.upbit.com/websocket/v1'
