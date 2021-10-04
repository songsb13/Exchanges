def sai_to_upbit_symbol_converter(pair):
    return pair.replace('_', '-')


def upbit_to_sai_symbol_converter(pair):
    return pair.replace('-', '_')


def sai_to_upbit_trade_type_converter(trade_type):
    actual_trade_type = dict(
        BUY_MARKET='price',
        BUY_LIMIT='limit',
        SELL_MARKET='market',
        SELL_LIMIT='limit',
    )

    return actual_trade_type.get(trade_type, trade_type)
