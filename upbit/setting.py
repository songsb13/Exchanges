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
    ORDERS = '/orders'
    CURRENCY = '/market/all'
    WITHDRAW = '/withdraws/coin'
    ACCOUNT = '/accounts'
    ORDERBOOK = '/orderbook'
    DEPOSIT_ADDRESS = '/v1/deposits/coin_addresses'
    GET_DEPOSIT_HISTORY = '/deposits'

    class Websocket(object):
        BASE = 'wss://api.upbit.com/websocket/v1'

    class Web(object):
        BASE = 'https://api-manager.upbit.com/api/v1'
        TRANSACTION_FEE_PAGE = '/kv/UPBIT_PC_COIN_DEPOSIT_AND_WITHDRAW_GUIDE'


class DepositStatus(object):
    SUBMITTING = 'submitting'
    SUBMITTED = 'submitted'
    ALMOST_ACCEPTED = 'almost_accepted'
    REJECTED = 'rejected'
    ACCEPTED = 'accepted'
    PROCESSING = 'processing'


class OrderStatus(object):
    """
        - wait : 체결 대기 (default)
        - watch : 예약주문 대기
        - done : 전체 체결 완료
        - cancel : 주문 취소
    """

    WAIT = 'wait'
    WATCH = 'watch'
    DONE = 'done'
    CANCEL = 'cancel'
