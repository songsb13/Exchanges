class UpbitConverter(object):
    # 각 exchange의 converter의 함수 이름은 동일해야함
    @staticmethod
    def sai_to_exchange(sai_symbol):
        return sai_symbol.replace("_", "-")

    @staticmethod
    def sai_to_exchange_subscriber(sai_symbol):
        return UpbitConverter.sai_to_exchange(sai_symbol)

    @staticmethod
    def exchange_to_sai(symbol):
        return symbol.replace("-", "_")

    @staticmethod
    def exchange_to_sai_subscriber(symbol):
        return UpbitConverter.exchange_to_sai(symbol)

    @staticmethod
    def sai_to_exchange_trade_type(trade_type):
        actual_trade_type = dict(
            BUY_MARKET="price",
            BUY_LIMIT="limit",
            SELL_MARKET="market",
            SELL_LIMIT="limit",
        )

        return actual_trade_type.get(trade_type, trade_type)
