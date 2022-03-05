class UpbitConverter(object):
    @staticmethod
    def sai_to_exchange(pair):
        return pair.replace('_', '-')

    @staticmethod
    def exchange_to_sai(pair):
        return pair.replace('-', '_')

    @staticmethod
    def sai_to_exchange_trade_type(trade_type):
        actual_trade_type = dict(
            BUY_MARKET='price',
            BUY_LIMIT='limit',
            SELL_MARKET='market',
            SELL_LIMIT='limit',
        )

        return actual_trade_type.get(trade_type, trade_type)
