from enum import Enum


class Tickets(Enum):
    """
        upbit는 개별 ticket값으로 구분함, 유니크 id로 구분
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