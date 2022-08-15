"""
setting of whole exchanges
"""

import os
import datetime
import copy

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "simple": {"format": "[%(name)s][%(message)s]"},
        "complex": {
            "format": "[%(asctime)s][%(levelname)s][%(filename)s][%(funcName)s][%(message)s]"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "DEBUG",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"parent": {"level": "INFO"}, "parent.child": {"level": "DEBUG"}},
}



class Tickets(object):
    """
    1~1000: public
    1001~2000: private
    """

    ORDERBOOK = 10
    CANDLE = 20


class Consts(object):

    ASKS = "asks"
    BIDS = "bids"

    MARKET = "market"
    LIMIT = "limit"
    CANDLE_LIMITATION = 100
    ORDERBOOK_LIMITATION = 20

    CANDLE = "candle"
    ORDERBOOK = "orderbook"
    TICKER = "ticker"
    BALANCE = "balance"
    DEPOSIT_ADDRESS = "deposit_address"
    TRANSACTION_FEE = "transaction_fee"

    NOT_FOUND = "not found"

    BID_PRICE_KEY = "bid_price"
    ASK_PRICE_KEY = "ask_price"

    BID_AMOUNT_KEY = "bid_amount"
    ASK_AMOUNT_KEY = "ask_amount"


class BaseMarkets(object):
    BTC = "BTC"
    ETH = "ETH"
    USDT = "USDT"


class BaseTradeType(object):
    BUY_MARKET = "BUY_MARKET"
    BUY_LIMIT = "BUY_LIMIT"
    SELL_MARKET = "SELL_MARKET"
    SELL_LIMIT = "SELL_LIMIT"


class SaiOrderStatus(object):
    OPEN = "open"
    ON_TRADING = "on_trading"
    CLOSED = "closed"

class SetLogger(object):
    """
        각 프로세스마다 별도의 로깅 파일을 가진다.
        기록되는 datetime은 UTC를 기본으로 한다.
        경로: /logs/{process_name}/{Y-m-d}/{H:M:S}

        1. 로테이팅 정책
            1. 날짜별 폴더
            2. maxBytes=10 * 1024 * 1024
            3. 파일명은 로깅 시작 datetime
        2. 로깅 정책
            1. Debug
                - 클래스단위, 함수단위에 들어가고 나갈때 작성한다.
                - prefix는 [datetime][level][process_name][function][parameters][message]순
                    ex) [2022-05-15T15:30:30][monitoring][get_deposit_addrs][ad='adff'][fail..]
                - 메세지는 영어로 작성한다.
            2. Info
                - 유저에게 notice하기 위한 로깅.
                - 별도 prefix없이 메세지만 기록한다.
                - 한국어로 작성한다.
            3. Warning
                - prefix는 debug와 동일하다.
                - 함수단위에서 실패해서 재시도할때 등 프로그램이 지속가능한 에러 수준일 때 기록한다.
            4. Error
                - prefix는 debug와 동일하다.
                - 함수단위에서 재시도가 더이상 안되는 등 프로그램이 지속불가능한 에러 수준일 때 기록한다.
            5. Critical
                - prefix는 debug와 동일하다.
                - 외부 요인이 아닌 Memory leak, 코드에서 발생하는 에러 수준일 때 기록한다.
    """
    @staticmethod
    def get_config_base_process(process_name):
        try:
            now = datetime.datetime.now()
            now_date, now_hour = str(now.date()), now.strftime("%Hh%Mm%Ss")

            log_path = os.path.join(ROOT_DIR, "Logs")
            SetLogger.create_dir(log_path)

            log_process_path = os.path.join(log_path, process_name)
            SetLogger.create_dir(log_process_path)

            log_date_path = os.path.join(log_process_path, now_date)
            SetLogger.create_dir(log_date_path)

            copied_base_config = copy.deepcopy(BASE_LOGGING_CONFIG)

            copied_base_config["handlers"][process_name] = {
                "class": "logging.FileHandler",
                "filename": os.path.join(log_date_path, f"{now_hour}.log"),
                "formatter": "complex",
                "level": "DEBUG",
            }
            copied_base_config["root"]["handlers"].append(process_name)

            return copied_base_config

        except Exception as ex:
            print(ex)

    @staticmethod
    def create_dir(path):
        if not os.path.isdir(path):
            os.mkdir(path)
