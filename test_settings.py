from DiffTrader.GlobalSetting.settings import DEBUG, DEBUG_ORDER_ID

from Exchanges.objects import DataStore, ExchangeResult, BaseExchange

import decimal
from decimal import Decimal

decimal.getcontext().prec = 8


def trade_result_mock(price=0.005353, amount=1.1233):
    return ExchangeResult(
        True,
        {
            'sai_average_price': Decimal(price),
            'sai_amount': Decimal(amount),
            'sai_order_id': DEBUG_ORDER_ID,
            'avg_price': Decimal(0.0014),
            'volume': Decimal(1.1233)
        }
    )
