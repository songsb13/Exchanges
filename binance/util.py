from Exchanges.settings import BaseMarkets


def _symbol_localizing(symbol):
    actual_symbol = dict(
        BCH='BCC'
    )
    return actual_symbol.get(symbol, symbol)


def _symbol_customizing(symbol):
    actual_symbol = dict(
        BCC='BCH'
    )

    return actual_symbol.get(symbol, symbol)


def sai_to_binance_symbol_converter(symbol):
    # BTC_XRP -> xrpbtc
    if '_' not in symbol:
        return symbol

    market, trade = symbol.split('_')
    return '{}{}'.format(_symbol_localizing(trade), market).lower()


def binance_to_sai_symbol_converter(symbol):
    # xrpbtc -> BTC_XRP
    if '_' in symbol:
        return symbol
    
    if symbol.endswith(BaseMarkets.BTC):
        market = BaseMarkets.BTC
        coin = symbol.replace(market)
    elif symbol.endswith(BaseMarkets.ETH):
        market = BaseMarkets.ETH
        coin = symbol.replace(market)
    elif symbol.endswith(BaseMarkets.USDT):
        market = BaseMarkets.USDT
        coin = symbol.replace(market)
    else:
        return None

    return '{}_{}'.format(market, _symbol_customizing(coin)).upper()


def sai_to_binance_trade_type_converter(trade_type):
    actual_trade_type = dict(
        MARKET='market',
        LIMIT='limit'
    )

    return actual_trade_type.get(trade_type, trade_type)