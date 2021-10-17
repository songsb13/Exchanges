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
    ABLE_WITHDRAWS = '/withdraws/chance'
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


class LocalConsts(object):
    AVAILABLE_MARKETS = ['KRW', 'BTC', 'USDT']
    LOT_SIZES = {
        'KRW': {'minimum': 5000, 'maximum': 1000000000},
        'BTC': {'minimum': 0.0005, 'maximum': 20},
        'USDT': {'minimum': 0.0005, 'maximum': 1000000}
    }

    STEP_SIZE = {
        'KRW': [(2000000, 1000), (1000000, 500), (500000, 100),
                (100000, 50), (10000, 10), (1000, 5), (100, 1),
                (10, 0.1), (1, 0.01), (0.1, 0.001), ('-inf', 0.0001)],
        'BTC': [('-inf', 0.00000001)],
        'USDT': [('-inf', 0.001)]
    }
