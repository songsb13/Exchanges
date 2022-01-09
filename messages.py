class WarningMessage(object):
    MESSAGE_NOT_FOUND = '[{name}]응답 메세지를 찾을 수 없습니다.'
    ORDERBOOK_NOT_STORED = '[{name}]오더북 데이터를 찾을 수 없습니다.'
    CANDLE_NOT_STORED = '[{name}]캔들 데이터를 찾을 수 없습니다.'
    PRECISION_NOT_FOUND = '[{name}]호가 정보를 찾을 수 없습니다.'
    TRANSACTION_FAILED = '[{name}] 출금 비용 정보를 찾을 수 없습니다.'
    EXCEPTION_RAISED = '[{name}] 정상적으로 프로그램이 동작하지 않았습니다. 작성자에게 문의 부탁드립니다.'
    FAIL_MESSAGE_BODY = '[{name}] 정상적으로 동작하지 않았습니다. 원인은 다음과 같습니다. [{message}]'
    WRONG_LOT_SIZE = '[{name}] 정상적인 주문 금액이 아닙니다. ' \
                     '해당 거래소의 [{market}]마켓은 주문 금액이 [{minimum}]이상 [{maximum}]미만이 되어야 합니다.'
    STEP_SIZE_NOT_FOUND = '[{name}] 정상적인 호가범위가 아닙니다. ' \
                          '해당 거래소의 [{sai_symbol}]를 찾을 수 없습니다.'
    
    WRONG_MIN_NOTIONAL = '[{name}]정상적인 주문 금액이 아닙니다. ' \
                         '해당 거래소의 [{symbol}]는 주문 총액이 [{min_notional}]이상이어야 합니다.'
    FAIL_RESPONSE_DETAILS = '{name}, body: [{body}], path: [{path}], parameter: [{parameter}]'

    HAS_NO_WITHDRAW_ID = '[{name}] 데이터에 해당 출금 ID가 존재하지 않습니다. = [{withdrawal_id}]'


class CriticalMessage(object):
    pass


class DebugMessage(object):
    ENTRANCE = '{name}, fn={fn}, data={data}'
    FATAL = 'FATAL, {name}, fn={fn}'
