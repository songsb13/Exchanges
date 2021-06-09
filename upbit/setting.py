from enum import Enum


class Tickets(Enum):
    """
        upbit는 개별 ticket값으로 구분함, 유니크 id로 구분
        1~1000: public
        1001~2000: private
    """
    ORDERBOOK = 10
    CANDLE = 20
