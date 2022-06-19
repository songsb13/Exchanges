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


def sai_to_binance_converter(pair):
    # BTC_XRP -> xrpbtc
    market, trade = pair.split('_')
    return '{}{}'.format(_symbol_localizing(trade), market).lower()


def binance_to_sai_converter(pair):
    market, trade = pair[-3:], pair[:-3]
    
    return '{}_{}'.format(market, _symbol_customizing(trade)).upper()
