from Exchanges.settings import BaseMarkets


def symbol_localizing(symbol):
    actual_symbol = dict(
        BCH='BCC'
    )
    return actual_symbol.get(symbol, symbol)


def symbol_customizing(symbol):
    actual_symbol = dict(
        BCC='BCH'
    )

    return actual_symbol.get(symbol, symbol)


class BinanceConverter(object):
    @staticmethod
    def sai_to_exchange(sai_symbol):
        # BTC_XRP -> XRPBTC
        if '_' not in sai_symbol:
            return sai_symbol

        market, trade = sai_symbol.split('_')
        return '{}{}'.format(symbol_localizing(trade), market).upper()

    @staticmethod
    def sai_to_exchange_subscriber(sai_symbol):
        # BTC_XRP -> xrpbtc
        return BinanceConverter.sai_to_exchange(sai_symbol).lower()

    @staticmethod
    def exchange_to_sai(symbol):
        # xrpbtc -> BTC_XRP
        if '_' in symbol:
            return symbol

        if symbol.endswith(BaseMarkets.BTC):
            market = BaseMarkets.BTC
        elif symbol.endswith(BaseMarkets.ETH):
            market = BaseMarkets.ETH
        elif symbol.endswith(BaseMarkets.USDT):
            market = BaseMarkets.USDT
        else:
            return None

        coin = symbol.replace(market, '')
        return '{}_{}'.format(market, symbol_customizing(coin)).upper()

    @staticmethod
    def exchange_to_sai_subscriber(symbol):
        return BinanceConverter.exchange_to_sai(symbol).upper()

    @staticmethod
    def sai_to_exchange_trade_type(trade_type):
        actual_trade_type = dict(
            BUY_MARKET='market',
            BUY_LIMIT='limit',
            SELL_MARKET='market',
            SELL_LIMIT='limit',
        )

        return actual_trade_type.get(trade_type, trade_type)