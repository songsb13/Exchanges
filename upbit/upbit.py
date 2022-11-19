from Exchanges.upbit.apis import UpbitAPI
import datetime


class SaiOrderStatus(object):
    OPEN = "open"
    ON_TRADING = "on_trading"
    CLOSED = "closed"


class ExchangeResult(object):
    def __init__(self, success, data=None, message="", wait_time=0):
        self.success = success
        self.data = data
        self.message = message
        self.wait_time = wait_time


class SAIDataValidator(object):
    def _has_key(self, dic, required):
        key = set(dic.keys())
        return key == key.intersection(required)

    def generate_sai_data_dict(self, required, key_list, data_dict):
        if not self._has_key(data_dict, required):
            return

        sai_dict = dict()
        for key, type_ in key_list:
            sai_dict[f"sai_{key}"] = data_dict.get(type_(key), Consts.NOT_FOUND)

        return sai_dict

    def withdrawal(self, data_dict):
        key_list = [
            ("address", str),
            ("amount", decimal.Decimal),
            ("time", str),
            ("coin", str),
            ("network", str),
            ("fee", decimal.Decimal),
            ("id", str),
        ]
        required = ("amount", "coin", "id")

        return self.generate_sai_data_dict(required, key_list, data_dict)

    def trade(self, data_dict):
        key_list = [
            ("average_price", decimal.Decimal),
            ("amount", decimal.Decimal),
            ("id", str),
        ]

        required = ("average_price", "amount", "id")

        return self.generate_sai_data_dict(required, key_list, data_dict)


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


class Upbit(object):
    def __init__(self, key, secret):
        self.__api = UpbitAPI(key, secret)
        self.__validator = SAIDataValidator()
        self.__converter = UpbitConverter

    def get_deposit_history(self, coin, number):
        result = self.__api.get_accepted_deposits(coin)
        return ExchangeResult(
            success=True,
            data={
                "sai_deposit_amount": result[number]["amount"],
                "sai_coin": result[number]["currency"]
            }
        )

    def get_order_history(self, uuid):
        result = self.__api.get_order_history(uuid)

        price_list, amount_list = [], []
        for each in result["trades"]:
            total_price = float(each["price"]) * float(each["volume"])
            price_list.append(float(total_price))
            amount_list.append(float(each["volume"]))

        if price_list:
            avg_price = float(sum(price_list) / len(price_list))
            total_amount = sum(amount_list)
            return ExchangeResult(
                success=True,
                data={
                    "sai_status": SaiOrderStatus.CLOSED,
                    "sai_average_price": Decimal(avg_price),
                    "sai_amount": Decimal(total_amount),
                }
            )
        else:
            return ExchangeResult(
                success=False,
                data=dict()
            )

    def get_available_symbols(self):
        result = self.__api.get_all_market()

        sai_symbol_list = []
        for each in result:
            symbol = each.get("market")
            if symbol:
                converted = self.__converter.exchange_to_sai(symbol)
                sai_symbol_list.append(converted)
        else:
            return ExchangeResult(
                success=True,
                data=sai_symbol_list
            )

    def get_trading_fee(self):
        context = Context(prec=8)
        dic_ = dict(
            BTC=context.create_decimal_from_float(0.0025),
            KRW=context.create_decimal_from_float(0.0005),
            USDT=context.create_decimal_from_float(0.0025),
        )

        return ExchangeResult(True, dic_)

    def is_withdrawal_completed(self, coin, uuid):
        result = self.__api.get_completed_withdraw_history(
            coin,
            uuid
        )

        for history in result:
            if history["uuid"] == uuid:
                raw = {
                    "amount": history["amount"],
                    "time": datetime.datetime.fromisoformat(history["done_at"]),
                    "coin": history["currency"],
                    "fee": history["fee"],
                    "id": history["txid"]
                }
                sai_dict = self.__validator.withdrawal(raw)

                return ExchangeResult(
                    success=True,
                    data={raw, sai_dict},
                )
        else:
            return ExchangeResult(
                success=False,
            )
