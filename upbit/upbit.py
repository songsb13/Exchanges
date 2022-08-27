import jwt
import time
import json
import aiohttp
import requests
import datetime

from websocket import WebSocketConnectionClosedException
from urllib.parse import urlencode


from Exchanges.settings import Consts, SaiOrderStatus, BaseTradeType, SetLogger, DEBUG
from Exchanges.test_settings import trade_result_mock
from Exchanges.messages import WarningMessage
from Exchanges.messages import DebugMessage

from Exchanges.upbit.setting import (
    DepositStatus,
    LocalConsts,
    WithdrawalStatus,
    Tickets
)
from Exchanges.upbit.util import UpbitConverter

from Exchanges.objects import (
    ExchangeResult,
    BaseExchange,
    BaseSubscriber
)

from decimal import Decimal, getcontext, Context
import logging.config


__file__ = "upbit.py"

logging_config = SetLogger.get_config_base_process(__file__)
logging.config.dictConfig(logging_config)

getcontext().prec = 8


class UpbitSubscriber(BaseSubscriber):
    base_url = "https://api-manager.upbit.com/api/v1"
    name = "Upbit Subscriber"
    converter = UpbitConverter
    base_logger = logging

    def __init__(self, data_store, lock_dic):
        """
        data_store: An object for storing orderbook&candle data, using orderbook&candle queue in this object.
        lock_dic: dictionary for avoid race condition, {orderbook: Lock, candle: Lock}
        """
        logging.debug(f"{self.name}::: start")

        super(UpbitSubscriber, self).__init__()

        self.data_store = data_store
        self._lock_dic = lock_dic

    def subscribe_orderbook(self):
        logging.debug(f"{self.name}::: subscribe_orderbook")
        self._subscribe_dict[Consts.ORDERBOOK] = [
            {
                "ticket": Tickets.ORDERBOOK,
            },
            {
                "type": Consts.ORDERBOOK,
                "codes": list(self._orderbook_symbol_set),
                "isOnlyRealtime": True,
            },
        ]
        self._send_with_subscribe_set()

    def subscribe_candle(self):
        logging.debug(f"{self.name}::: subscribe_candle")
        self._subscribe_dict[Consts.CANDLE] = [
            {
                "ticket": Tickets.CANDLE,
            },
            {"type": Consts.TICKER, "codes": list(self._candle_symbol_set)},
        ]

        self._send_with_subscribe_set()

    def on_message(self, *args):
        obj_, message = args
        try:
            data = json.loads(message.decode())
            type_ = data["type"]
            if type_ == Consts.ORDERBOOK:
                self.orderbook_receiver(data)
            elif type_ == Consts.TICKER:
                self.candle_receiver(data)
        except WebSocketConnectionClosedException as ex:
            logging.debug("Disconnected orderbook websocket.")
            self.stop()
            raise ex

        except Exception as ex:
            logging.exception("Unexpected error from Websocket thread.")
            self.stop()
            raise ex

    def orderbook_receiver(self, data):
        with self._lock_dic[Consts.ORDERBOOK]:
            symbol = data["code"]
            sai_symbol = self.converter.exchange_to_sai(symbol)

            data_keys = {
                Consts.BID_PRICE_KEY: "bid_price",
                Consts.BID_AMOUNT_KEY: "bid_size",
                Consts.ASK_PRICE_KEY: "ask_price",
                Consts.ASK_AMOUNT_KEY: "ask_size",
            }

            total = self.temp_orderbook_setter(data["orderbook_units"], data_keys)
            self.data_store.orderbook_queue[sai_symbol] = total

    def candle_receiver(self, data):
        with self._lock_dic[Consts.CANDLE]:
            symbol = data["code"]
            sai_symbol = self.converter.exchange_to_sai(symbol)
            candle_list = [
                data["opening_price"],
                data["high_price"],
                data["low_price"],
                data["trade_price"],
                data["trade_volume"],
                data["trade_timestamp"],
            ]

            store_list = self.temp_candle_setter(
                self.data_store.candle_queue[sai_symbol], candle_list
            )

            self.data_store.candle_queue[sai_symbol] = store_list

    def unsubscribe_orderbook(self, symbol):
        logging.debug(f"{self.name}::: unsubscribe_orderbook")

        self._remove_contents(symbol, self._orderbook_symbol_set)

    def unsubscribe_candle(self, symbol):
        logging.debug(f"{self.name}::: unsubscribe_candle")

        self._remove_contents(symbol, self._candle_symbol_set)

    def _remove_contents(self, symbol, symbol_set):
        try:
            symbol_set.remove(symbol)
        except Exception as ex:
            logging.debug(f"{self.name}::: remove error, [{ex}]")

    def _send_with_subscribe_set(self):
        data = list()
        for key, item in self._subscribe_dict.items():
            data += self._subscribe_dict[key]

        self._websocket_app.send(str(data))


class BaseUpbit(BaseExchange):
    name = "Upbit"
    converter = UpbitConverter
    exchange_subscriber = UpbitSubscriber
    base_url = "https://api.upbit.com/v1"
    error_key = "error"
    base_logger = logging

    def __init__(self, key, secret):
        super(BaseUpbit, self).__init__()
        self._key = key
        self._secret = secret

    def __str__(self):
        return self.name

    def get_balance(self, cached=False):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_balance", data=str(locals())
            )
        )
        if cached:
            return self.get_cached_data(Consts.BALANCE)
        result = self._private_api("GET", "/accounts")

        if result.success:
            result.data = {bal["currency"]: bal["balance"] for bal in result.data}
            self.set_cached_data(Consts.BALANCE, result.data)
        return result

    def get_ticker(self, sai_symbol, cached=False):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_ticker", data=str(locals())
            )
        )
        symbol = self.converter.sai_to_exchange(sai_symbol)

        if cached:
            return self.get_cached_data(Consts.TICKER, sai_symbol)

        result = self._public_api("/ticker", {"markets": symbol})

        if result.success:
            ticker = Decimal(result.data[0]["trade_price"])
            result.data = {"sai_price": ticker}
            self.set_cached_data(Consts.TICKER, result.data)

        return result

    def get_available_symbols(self):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_available_symbols", data=""
            )
        )
        result = self._public_api("/market/all")

        if result.success:
            result_list = list()
            for data in result.data:
                symbol = data.get("market")
                if symbol:
                    converted = self.converter.exchange_to_sai(symbol)
                    result_list.append(converted)
            else:
                return ExchangeResult(True, data=result_list)
        else:
            return result

    def get_order_history(self, uuid, additional_parameter):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_order_history", data=str(locals())
            )
        )
        params = dict(uuid=uuid)

        result = self._private_api("GET", "/order", params)

        if result.success:
            price_list, amount_list = list(), list()
            for each in result.data["trades"]:
                total_price = float(each["price"]) * float(each["volume"])
                price_list.append(float(total_price))
                amount_list.append(float(each["volume"]))

            if price_list:
                avg_price = float(sum(price_list) / len(price_list))
                total_amount = sum(amount_list)
                additional = {
                    "sai_status": SaiOrderStatus.CLOSED,
                    "sai_average_price": Decimal(avg_price),
                    "sai_amount": Decimal(total_amount),
                }

                result.data = additional
            else:
                result.success = False

        return result

    def get_deposit_history(self, coin, number):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_deposit_history", data=str(locals())
            )
        )
        params = dict(currency=coin, state=DepositStatus.ACCEPTED)
        result = self._private_api("GET", "/deposits", params)

        if result.success:
            latest_data = result.data[:number]
            result_dict = dict(
                sai_deposit_amount=latest_data["amount"],
                sai_coin=latest_data["currency"],
            )
            result.data = result_dict

        return result

    def get_trading_fee(self):
        context = Context(prec=8)
        dic_ = dict(
            BTC=context.create_decimal_from_float(0.0025),
            KRW=context.create_decimal_from_float(0.0005),
            USDT=context.create_decimal_from_float(0.0025),
        )

        return ExchangeResult(True, dic_)

    async def get_deposit_addrs(self, cached=False, avoid_coin_list=None):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_deposit_addrs", data=str(locals())
            )
        )

        if avoid_coin_list is None:
            avoid_coin_list = list()
        if cached:
            return self.get_cached_data(Consts.DEPOSIT_ADDRESS)
        address_result = await self._async_private_api("GET", "/deposits/coin_addresses")
        if address_result.success:
            result_dict = dict()
            for data in address_result.data:
                coin = data["currency"]
                if coin in avoid_coin_list:
                    continue

                able_result = await self._async_private_api(
                    "GET", "/withdraws/chance", {"currency": coin}
                )

                if not able_result.success:
                    continue

                support_list = able_result.data["currency"]["wallet_support"]
                if "withdraw" not in support_list or "deposit" not in support_list:
                    continue

                deposit_address = data["deposit_address"]

                if "secondary_address" in data.keys() and data["secondary_address"]:
                    result_dict[coin + "TAG"] = data["secondary_address"]

                result_dict[coin] = deposit_address

            address_result.data = result_dict
            self.set_cached_data(Consts.DEPOSIT_ADDRESS, address_result.data)
            self._cached_data[Consts.DEPOSIT_ADDRESS] = {
                "data": address_result.data,
                "cached_time": time.time(),
            }

        return address_result

    async def get_transaction_fee(self, cached=False):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_transaction_fee", data=str(locals())
            )
        )

        if cached:
            self.get_cached_data(Consts.TRANSACTION_FEE)

        async with aiohttp.ClientSession() as s:
            url = "https://api-manager.upbit.com/api/v1/kv/UPBIT_PC_COIN_DEPOSIT_AND_WITHDRAW_GUIDE"
            rq = await s.get(url)

            result_text = await rq.text()
        raw_data = json.loads(result_text)

        success = raw_data.get("success", False)
        if not success:
            return ExchangeResult(
                False,
                "",
                message=WarningMessage.TRANSACTION_FAILED.format(name=self.name),
            )

        data = json.loads(raw_data["data"])

        fees = dict()
        context = Context(prec=8)
        for each in data:
            coin = each["currency"]
            withdraw_fee = context.create_decimal(each["withdrawFee"])
            fees.update({coin: withdraw_fee})
        self.set_cached_data(Consts.BALANCE, fees)
        return ExchangeResult(True, fees)

    def buy(self, sai_symbol, trade_type, amount=None, price=None):
        logging.debug(
            DebugMessage.ENTRANCE.format(name=self.name, fn="buy", data=str(locals()))
        )

        if not price:
            return ExchangeResult(False, message="")

        if BaseTradeType.BUY_LIMIT and not amount:
            return ExchangeResult(False, message="")

        upbit_trade_type = self.converter.sai_to_exchange_trade_type(trade_type)
        symbol = self.converter.sai_to_exchange(sai_symbol)

        default_parameters = {
            "market": symbol,
            "side": "bid",
            "ord_type": upbit_trade_type,
        }
        # market trading
        if trade_type == BaseTradeType.BUY_MARKET:
            trading_validation_result = self._trading_validator_in_market(
                symbol, amount, trade_type
            )
            if not trading_validation_result.success:
                return trading_validation_result
            stepped_price = trading_validation_result.data
            default_parameters.update(dict(price=stepped_price))
        else:
            trading_validation_result = self._trading_validator(symbol, amount)

            if not trading_validation_result.success:
                return trading_validation_result
            stepped_price = trading_validation_result.data
            default_parameters.update(dict(price=stepped_price, volume=amount))

        if DEBUG:
            return trade_result_mock(price, amount)

        result = self._private_api("POST", "/orders", default_parameters)

        if result.success:
            raw_dict = {
                "average_price": Decimal(result.data["avg_price"]),
                "amount": Decimal(result.data["volume"]),
                "order_id": result.data["uuid"],
            }
            sai_dict = self._data_validator.trade(raw_dict)
            result.data.update(sai_dict)

        return result

    def sell(self, sai_symbol, trade_type, amount=None, price=None):
        logging.debug(
            DebugMessage.ENTRANCE.format(name=self.name, fn="sell", data=str(locals()))
        )

        if amount is None:
            return ExchangeResult(False, message="")

        if BaseTradeType.SELL_LIMIT and not price:
            return ExchangeResult(False, message="")

        upbit_trade_type = self.converter.sai_to_exchange_trade_type(trade_type)
        symbol = self.converter.sai_to_exchange(sai_symbol)

        default_parameters = {
            "market": symbol,
            "side": "ask",
            "volume": amount,
            "ord_type": upbit_trade_type,
        }
        if trade_type == BaseTradeType.SELL_MARKET:
            trading_validation_result = self._trading_validator_in_market(
                symbol, amount, trade_type
            )
            if not trading_validation_result.success:
                return trading_validation_result
        else:
            trading_validation_result = self._trading_validator(symbol, amount)

            if not trading_validation_result.success:
                return trading_validation_result
            stepped_price = trading_validation_result.data
            default_parameters.update(dict(price=stepped_price))

        if DEBUG:
            return trade_result_mock(price, amount)

        result = self._private_api("POST", "/orders", default_parameters)

        if result.success:
            raw_dict = {
                "average_price": Decimal(result.data["avg_price"]),
                "amount": Decimal(result.data["volume"]),
                "order_id": result.data["uuid"],
            }
            sai_dict = self._data_validator.trade(raw_dict)
            result.data.update(sai_dict)

        return result

    def withdraw(self, coin, amount, to_address, payment_id=None):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="withdraw", data=str(locals())
            )
        )
        params = {
            "currency": coin,
            "address": to_address,
            "amount": str(amount),
        }

        if payment_id:
            params.update({"secondary_address": payment_id})

        result = self._private_api("POST", "/withdraws/coin", params)

        if result.success:
            sai_data = {
                "sai_id": result.data["uuid"],
            }
            result.data = sai_data

        return result

    def is_withdrawal_completed(self, coin, uuid):
        logging.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="is_withdrawal_completed", data=str(locals())
            )
        )
        params = dict(currency=coin, uuid=uuid, state=WithdrawalStatus.DONE)
        result = self._private_api("GET", "/withdraws", params)

        if result.success and result.data:
            for history_dict in result.data:
                history_id = history_dict["uuid"]
                if history_id == uuid:
                    raw_dict = dict(
                        address=Consts.NOT_FOUND,
                        amount=Decimal(history_dict["amount"]),
                        time=datetime.datetime.fromisoformat(history_dict["done_at"]),
                        coin=history_dict["currency"],
                        network=Consts.NOT_FOUND,
                        fee=Decimal(history_dict["fee"]),
                        id=history_dict["txid"],
                    )
                    sai_dict = self._data_validator.withdrawal(raw_dict)
                    result_dict = {**history_dict, **sai_dict}

                    return ExchangeResult(success=True, data=result_dict)
            else:
                message = WarningMessage.HAS_NO_WITHDRAW_ID.format(
                    name=self.name, withdrawal_id=uuid
                )
                return ExchangeResult(success=False, message=message)
        else:
            return ExchangeResult(success=False, message=result.message)

    def _get_result(self, response, path, extra, fn, error_key=error_key):
        result_object = super(BaseUpbit, self)._get_result(
            response, path, extra, fn, error_key
        )
        if not result_object.success:
            raw_error_message = result_object.message.get("message", None)
            if raw_error_message is None:
                error_message = WarningMessage.FAIL_RESPONSE_DETAILS.format(
                    name=self.name, body=raw_error_message, path=path, parameter=extra
                )
            else:
                error_message = WarningMessage.MESSAGE_NOT_FOUND.format(name=self.name)

            result_object.message = error_message
            logging.debug(error_message)
        return result_object

    def _get_step_size(self, symbol, krw_price):
        market, coin = symbol.split("-")

        if market in ["BTC", "USDT"]:
            return ExchangeResult(True, LocalConsts.STEP_SIZE[market][0][1])

        for price, unit in LocalConsts.STEP_SIZE[market]:
            if krw_price >= price:
                decimal_price = Decimal(price)
                stepped_price = decimal_price - Decimal(decimal_price % unit)
                return ExchangeResult(True, stepped_price)
        else:
            sai_symbol = self.converter.exchange_to_sai(symbol)  # for logging
            return ExchangeResult(
                False,
                message=WarningMessage.STEP_SIZE_NOT_FOUND.format(
                    name=self.name,
                    sai_symbol=sai_symbol,
                ),
            )

    def _is_available_lot_size(self, symbol, krw_price, amount):
        market, coin = symbol.split("-")
        total_price = Decimal(krw_price * amount)

        minimum = LocalConsts.LOT_SIZES[market]["minimum"]
        maximum = LocalConsts.LOT_SIZES[market]["maximum"]
        if not minimum <= total_price <= maximum:
            msg = WarningMessage.WRONG_LOT_SIZE.format(
                name=self.name, market=market, minimum=minimum, maximum=maximum
            )
            return ExchangeResult(False, message=msg)

        return ExchangeResult(True)

    def _trading_validator_in_market(self, symbol, market_amount, trading_type):
        """
        validator for market
        Args:
            symbol: KRW, BTC
            amount: amount, Decimal
        Returns:
            True or False
            messages if getting false
        """
        market_current_price = 1

        if trading_type == BaseTradeType.SELL_MARKET:
            ticker_object = self.get_ticker(symbol)
            if not ticker_object.success:
                return ticker_object

            market_current_price = ticker_object.data["sai_price"]

        lot_size_result = self._is_available_lot_size(
            symbol, market_current_price, market_amount
        )

        if not lot_size_result.success:
            return lot_size_result

        step_size_result = self._get_step_size(symbol, market_amount)

        return step_size_result

    def _trading_validator(self, symbol, amount):
        """
        Args:
            symbol: KRW, BTC
            amount: amount, Decimal
        Returns:
            True or False
            messages if getting false
        """
        ticker_object = self.get_ticker(symbol)
        if not ticker_object.success:
            return ticker_object

        krw_price = ticker_object.data["sai_price"]

        lot_size_result = self._is_available_lot_size(symbol, krw_price, amount)

        if not lot_size_result.success:
            return lot_size_result

        step_size_result = self._get_step_size(symbol, krw_price)

        return step_size_result

    def _sign_generator(self, payload):
        token = "Bearer {}".format(
            jwt.encode(
                payload,
                self._secret,
            )
        )
        return {"Authorization": token}

    def _public_api(self, path, extra=None):
        return super(BaseUpbit, self)._public_api(path, extra)

    def _private_api(self, method, path, extra=None):
        logging.debug(
            DebugMessage.ENTRANCE.format(name=self.name, fn="_private_api", data=extra)
        )
        payload = {
            "access_key": self._key,
            "nonce": int(time.time() * 1000),
        }

        if extra is not None:
            payload.update({"query": urlencode(extra)})

        header = self._sign_generator(payload)
        url = self.base_url + path

        if method == "POST":
            rq = requests.post(url=url, headers=header, data=extra)

        else:
            rq = requests.get(url=url, headers=header, params=extra)

        return self._get_result(rq, path, extra, fn="private_api")

    async def _async_private_api(self, method, path, extra=None):
        payload = {
            "access_key": self._key,
            "nonce": int(time.time() * 1000),
        }

        if extra is not None:
            payload.update({"query": urlencode(extra)})

        header = self._sign_generator(payload)
        url = self.base_url + path

        async with aiohttp.ClientSession() as s:
            if method == "GET":
                rq = await s.get(url, headers=header, data=extra)
            else:
                rq = await s.post(url, headers=header, data=extra)

            result_text = await rq.text()
            return self._get_result(result_text, path, extra, fn="_async_private_api")


if __name__ == "__main__":
    import asyncio

    up = BaseUpbit("", "")
    up.set_subscriber()
    up.set_subscribe_orderbook(["KRW-XRP", "KRW-ETH"])
    while True:
        time.sleep(5)
        pk = asyncio.run(up.get_curr_avg_orderbook())
        print(pk)
