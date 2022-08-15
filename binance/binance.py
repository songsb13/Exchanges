import hmac
import hashlib
import requests
import time
import aiohttp

from decimal import getcontext, Context
import datetime

from urllib.parse import urlencode
from decimal import Decimal

from Exchanges.settings import Consts, BaseTradeType, SaiOrderStatus
from Exchanges.test_settings import trade_result_mock
from Exchanges.messages import WarningMessage, DebugMessage
from Exchanges.binance.util import (
    BinanceConverter,
    symbol_localizing,
    symbol_customizing,
)
from Exchanges.binance.setting import (
    Urls,
    OrderStatus,
    DepositStatus,
    WithdrawalStatus,
    FilterType,
)
from Exchanges.objects import ExchangeResult, BaseExchange
from Exchanges.binance.subscriber import BinanceSubscriber


getcontext().prec = 8


class Binance(BaseExchange):
    name = "Binance"
    converter = BinanceConverter
    exchange_subscriber = BinanceSubscriber
    base_url = "https://api.binance.com"
    error_key = "msg"

    def __init__(self, key, secret):
        super(Binance, self).__init__()
        self._key = key
        self._secret = secret

        self.exchange_info = None
        self.all_details = None
        self._step_sizes = None
        self._get_exchange_info()
        self._get_all_asset_details()
        self._symbol_details_dict = self._set_symbol_details()

    def __str__(self):
        return self.name

    def get_balance(self, cached=False):
        debugger.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_balance", data=str(locals())
            )
        )

        if cached and Consts.BALANCE:
            return self.get_cached_data(Consts.BALANCE)

        result_object = self._private_api("GET", "/api/v3/account")

        if result_object.success:
            balance = dict()
            for bal in result_object.data["balances"]:
                coin = bal["asset"]
                if float(bal["free"]) > 0:
                    balance[coin.upper()] = Decimal(bal["free"])

            result_object.data = balance
            self.set_cached_data(Consts.BALANCE, result_object.data)
        return result_object

    def get_ticker(self, sai_symbol, cached=False):
        debugger.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_ticker", data=str(locals())
            )
        )
        if cached:
            return self.get_cached_data(Consts.TICKER, sai_symbol)

        binance_symbol = self.converter.sai_to_exchange(sai_symbol)
        result_object = self._public_api("/api/v3/ticker/price", {"symbol": binance_symbol})
        if result_object.success:
            ticker = Decimal(result_object.data[0]["trade_price"])

            result_object.data = {"sai_price": ticker}
            self.set_cached_data(Consts.TICKER, result_object.data)

        return result_object

    def get_available_symbols(self):
        debugger.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_available_symbols", data=str(locals())
            )
        )
        result = list()
        for data in self.exchange_info["symbols"]:
            market = data.get("quoteAsset")
            coin = data.get("baseAsset")

            if not market or not coin:
                continue

            result.append("{}_{}".format(market, coin))

        return ExchangeResult(True, data=result)

    def get_order_history(self, order_id, additional):
        debugger.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_order_history", data=str(locals())
            )
        )

        params = dict(orderId=order_id)
        if additional:
            if "symbol" in additional:
                additional["symbol"] = self.converter.sai_to_exchange(
                    additional["symbol"]
                )
            params.update(additional)

        result = self._private_api("GET", "/api/v3/order", params)

        if result.success:
            cummulative_quote_qty = Decimal(result.data["cummulativeQuoteQty"])
            origin_qty = Decimal(result.data["origQty"])
            additional = {
                "sai_status": SaiOrderStatus.CLOSED
                if result.data["status"] == OrderStatus.FILLED
                else SaiOrderStatus.ON_TRADING,
                "sai_average_price": cummulative_quote_qty,
                "sai_amount": origin_qty,
            }

            result.data = additional

        return result

    def get_deposit_history(self, coin, number):
        debugger.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_deposit_history", data=str(locals())
            )
        )
        params = dict(coin=coin, status=DepositStatus.SUCCESS)

        result = self._private_api("GET", "/sapi/v1/capital/deposit/hisrec", params)

        if result.success and result.data:
            latest_data = result.data[:number]
            result_dict = dict(
                sai_deposit_amount=latest_data["amount"], sai_coin=latest_data["coin"]
            )

            result.data = result_dict

        return result

    def get_trading_fee(self):
        context = Context(prec=8)
        dic_ = dict(BTC=context.create_decimal_from_float(0.001))
        return ExchangeResult(True, dic_)

    async def get_deposit_addrs(self, cached=False, coin_list=None):
        debugger.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_deposit_addrs", data=str(locals())
            )
        )
        if cached:
            return self.get_cached_data(Consts.DEPOSIT_ADDRESS)

        able_to_trading_coin_set = set()
        for data in self.exchange_info["symbols"]:
            # check status coin is able to trading.
            if data["status"] == "TRADING":
                able_to_trading_coin_set.add(data["baseAsset"])

        able_to_trading_coin_set = ["BTC", "ETH", "XRP"]

        try:
            result_message = str()
            return_deposit_dict = dict()
            for coin in able_to_trading_coin_set:
                coin = symbol_customizing(coin)
                get_deposit_result_object = await self._async_private_api(
                    "GET", "/sapi/v1/capital/deposit/address", {"coin": coin.lower()}
                )

                if not get_deposit_result_object.success:
                    result_message += "[{}]해당 코인은 값을 가져오는데 실패했습니다.\n".format(
                        get_deposit_result_object.message
                    )
                    continue

                coin_details = self.all_details.get(coin, None)

                if coin_details is not None:
                    able_deposit = coin_details["depositAllEnable"]
                    able_withdrawal = coin_details["withdrawAllEnable"]

                    if not able_deposit:
                        debugger.debug(
                            "Binance, [{}] 해당 코인은 입금이 막혀있는 상태입니다.".format(coin)
                        )
                        continue

                    elif not able_withdrawal:
                        debugger.debug(
                            "Binance, [{}] 해당 코인은 출금이 막혀있는 상태입니다.".format(coin)
                        )
                        continue

                address = get_deposit_result_object.data.get("address")
                if address:
                    return_deposit_dict[coin] = address

                address_tag = get_deposit_result_object.data.get("tag")
                if "addressTag" in get_deposit_result_object.data:
                    return_deposit_dict[coin + "TAG"] = address_tag
            self.set_cached_data(Consts.DEPOSIT_ADDRESS, return_deposit_dict)
            return ExchangeResult(True, return_deposit_dict, result_message)

        except Exception as ex:
            debugger.exception("FATAL: Binance, get_deposit_addrs")

            return ExchangeResult(
                False,
                message=WarningMessage.EXCEPTION_RAISED.format(name=self.name),
                wait_time=1,
            )

    async def get_transaction_fee(self, cached=False):
        debugger.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="get_transaction_fee", data=str(locals())
            )
        )

        if cached:
            self.get_cached_data(Consts.TRANSACTION_FEE)

        result = self._private_api("GET", "/sapi/v1/capital/config/getall")
        if result.success:
            fees = dict()
            context = Context(prec=8)
            for each in result.data:
                coin = each["coin"]
                for network_info in each["networkList"]:
                    network_coin = network_info["coin"]

                    if coin == network_coin:
                        withdraw_fee = context.create_decimal(
                            network_info["withdrawFee"]
                        )
                        fees.update({coin: withdraw_fee})
                        break

            result.data = fees
            self.set_cached_data(Consts.BALANCE, fees)
        return result

    def buy(self, sai_symbol, trade_type, amount=None, price=None):
        debugger.debug(
            DebugMessage.ENTRANCE.format(name=self.name, fn="buy", data=str(locals()))
        )

        if not amount:
            return ExchangeResult(False, message="")

        if BaseTradeType.BUY_LIMIT and not price:
            return ExchangeResult(False, message="")

        binance_trade_type = self.converter.sai_to_exchange(trade_type)
        symbol = self.converter.sai_to_exchange(sai_symbol)

        default_parameters = {
            "symbol": symbol,
            "side": "buy",
            "type": binance_trade_type,
        }

        if trade_type == BaseTradeType.BUY_MARKET:
            trading_validation_result = self._trading_validator_in_market(
                symbol, amount
            )
            if not trading_validation_result.success:
                return trading_validation_result
            stepped_amount = trading_validation_result.data
            default_parameters.update(dict(quantity=stepped_amount))
        else:
            trading_validation_result = self._trading_validator(symbol, amount)
            if not trading_validation_result.success:
                return trading_validation_result
            stepped_amount = trading_validation_result.data
            default_parameters.update(dict(price=price, quantity=stepped_amount))

        if DEBUG:
            return trade_result_mock(price, amount)

        result = self._private_api("POST", "/api/v3/order", default_parameters)

        if result.success:
            raw_dict = {
                "average_price": Decimal(result.data["price"]),
                "amount": Decimal(result.data["origQty"]),
                "order_id": result.data["orderId"],
            }
            sai_dict = self._data_validator.trade(raw_dict)
            result.data.update(sai_dict)

        return result

    def sell(self, sai_symbol, trade_type, amount=None, price=None):
        debugger.debug(
            DebugMessage.ENTRANCE.format(name=self.name, fn="sell", data=str(locals()))
        )
        params = dict()

        binance_trade_type = self.converter.sai_to_exchange_trade_type(trade_type)
        symbol = self.converter.sai_to_exchange(sai_symbol)

        default_parameters = {
            "symbol": symbol,
            "side": "sell",
            "type": binance_trade_type,
        }
        if trade_type == BaseTradeType.SELL_MARKET:
            trading_validation_result = self._trading_validator_in_market(
                symbol, amount
            )
            if not trading_validation_result.success:
                return trading_validation_result
            stepped_amount = trading_validation_result.data
            default_parameters.update(dict(quantity=stepped_amount))
        else:
            trading_validation_result = self._trading_validator(symbol, amount)
            if not trading_validation_result.success:
                return trading_validation_result
            stepped_amount = trading_validation_result.data
            default_parameters.update(dict(price=price, quantity=stepped_amount))

        if DEBUG:
            return trade_result_mock(price, amount)

        result = self._private_api("POST", "/api/v3/order", params)

        if result.success:
            raw_dict = {
                "average_price": Decimal(result.data["price"]),
                "amount": Decimal(result.data["origQty"]),
                "order_id": result.data["orderId"],
            }
            sai_dict = self._data_validator.trade(raw_dict)
            result.data.update(sai_dict)

        return result

    def withdraw(self, coin, amount, to_address, payment_id=None):
        debugger.debug(
            DebugMessage.ENTRANCE.format(
                name=self.name, fn="withdraw", data=str(locals())
            )
        )
        coin = symbol_localizing(coin)
        params = {
            "coin": coin,
            "address": to_address,
            "amount": Decimal(amount),
            "name": "SAICDiffTrader",
        }

        if payment_id:
            tag_dic = {"addressTag": payment_id}
            params.update(tag_dic)

        result = self._private_api("POST", "/sapi/v1/capital/withdraw/apply", params)

        if result.success:
            sai_data = {
                "sai_id": str(result.data["id"]),
            }
            result.data = sai_data

        return result

    def is_withdrawal_completed(self, coin, id_):
        params = dict(coin=coin, status=WithdrawalStatus.COMPLETED)
        result = self._private_api("GET", "/sapi/v1/capital/withdraw/history", params)

        if result.success and result.data:
            for history_dict in result.data:
                history_id = history_dict["id"]
                if history_id == id_:
                    raw_dict = dict(
                        address=history_dict["address"],
                        amount=Decimal(history_dict["amount"]),
                        time=datetime.datetime.strptime(
                            history_dict["applyTime"], "%Y-%m-%d %H:%M:%S"
                        ),
                        coin=history_dict["coin"],
                        network=history_dict["network"],
                        fee=Decimal(history_dict["transactionFee"]),
                        id=history_dict["txId"],
                    )
                    sai_dict = self._data_validator.withdrawal(raw_dict)
                    result_dict = {**history_dict, **sai_dict}
                    return ExchangeResult(success=True, data=result_dict)
            else:
                message = WarningMessage.HAS_NO_WITHDRAW_ID.format(
                    name=self.name, withdrawal_id=history_id
                )
                return ExchangeResult(success=False, message=message)
        else:
            return ExchangeResult(success=False, message=result.message)

    def _get_exchange_info(self):
        for _ in range(3):
            result_object = self._public_api("/api/v3/exchangeInfo")
            if result_object.success:
                self.exchange_info = result_object.data
                break

            time.sleep(result_object.wait_time)
        return result_object

    def _get_all_asset_details(self):
        for _ in range(3):
            result_object = self._private_api("GET", "/sapi/v1/capital/config/getall")
            if result_object.success:
                result = dict()
                for each in result_object.data:
                    coin = each.pop("coin", None)

                    if coin:
                        result.update({coin: each})
                self.all_details = result
                break

            time.sleep(result_object.wait_time)
        else:
            return result_object

    def _get_step_size(self, symbol, amount):
        step_size = self._symbol_details_dict.get(symbol, dict()).get("step_size")

        if not step_size:
            sai_symbol = self.converter.exchange_to_sai(symbol)
            return ExchangeResult(
                False,
                message=WarningMessage.STEP_SIZE_NOT_FOUND.format(
                    name=self.name,
                    sai_symbol=sai_symbol,
                ),
            )
        step_size = self._symbol_details_dict[symbol]["step_size"]

        decimal_amount = Decimal(amount)
        stepped_amount = decimal_amount - Decimal(decimal_amount % step_size)

        return ExchangeResult(True, stepped_amount)

    def _set_symbol_details(self):
        _symbol_details_dict = dict()
        for each in self.exchange_info["symbols"]:
            symbol = each["symbol"]
            filter_data = each["filters"]
            _symbol_details_dict.setdefault(symbol, dict())
            for filter_ in filter_data:
                filter_type = filter_["filterType"]
                if filter_type == FilterType.LOT_SIZE:
                    min_ = filter_.get("minQty", int())
                    max_ = filter_.get("maxQty", int())
                    step_size = filter_.get("stepSize", int())
                    _symbol_details_dict[symbol].update(
                        {
                            "min_quantity": Decimal(min_),
                            "max_quantity": Decimal(max_),
                            "step_size": Decimal(step_size),
                        }
                    )
                    break
                elif filter_type == FilterType.MIN_NOTIONAL:
                    min_notional = Decimal(filter_.get("minNotional", int()))
                    _symbol_details_dict[symbol].update({"min_notional": min_notional})
        return _symbol_details_dict

    def _is_available_lot_size(self, symbol, amount):
        minimum = self._symbol_details_dict[symbol]["min_quantity"]
        maximum = self._symbol_details_dict[symbol]["max_quantity"]
        if not minimum <= amount <= maximum:
            msg = WarningMessage.WRONG_LOT_SIZE.format(
                name=self.name, market=symbol, minimum=minimum, maximum=maximum
            )
            return ExchangeResult(False, message=msg)

        return ExchangeResult(True)

    def _is_available_min_notional(self, symbol, price, amount):
        total_price = Decimal(price * amount)

        minimum = self._symbol_details_dict[symbol].get("min_notional", 0)
        if not minimum <= total_price:
            msg = WarningMessage.WRONG_MIN_NOTIONAL.format(
                name=self.name,
                symbol=symbol,
                min_notional=minimum,
            )
            return ExchangeResult(False, message=msg)

        return ExchangeResult(True)

    def _trading_validator_in_market(self, symbol, amount):
        price = 1

        lot_size_result = self._is_available_lot_size(symbol, amount)

        if not lot_size_result.success:
            return lot_size_result

        min_notional_result = self._is_available_min_notional(symbol, price, amount)

        if not min_notional_result.success:
            return min_notional_result

        step_size_result = self._get_step_size(symbol, amount)

        return step_size_result

    def _trading_validator(self, symbol, amount):
        ticker_object = self.get_ticker(symbol)
        if not ticker_object.success:
            return ticker_object

        price = ticker_object.data["sai_price"]

        lot_size_result = self._is_available_lot_size(symbol, amount)

        if not lot_size_result.success:
            return lot_size_result

        min_notional_result = self._is_available_min_notional(symbol, price, amount)

        if not min_notional_result.success:
            return min_notional_result

        step_size_result = self._get_step_size(symbol, amount)

        return step_size_result

    def _get_result(self, response, path, extra, fn, error_key=error_key):
        result_object = super(Binance, self)._get_result(
            response, path, extra, fn, error_key
        )
        if not result_object.success:
            error_message = WarningMessage.FAIL_RESPONSE_DETAILS.format(
                name=self.name, body=result_object.message, path=path, parameter=extra
            )
            result_object.message = error_message
        return result_object

    def _sign_generator(self, payload):
        if payload is None:
            payload = dict()
        payload.update({"timestamp": int(time.time() * 1000)})

        sign = hmac.new(
            self._secret.encode("utf-8"),
            urlencode(sorted(payload.items())).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        payload.update({"signature": sign})

        return payload

    def _public_api(self, path, extra=None):
        return super(Binance, self)._public_api(path, extra)

    def _private_api(self, method, path, extra=None):
        debugger.debug(
            DebugMessage.ENTRANCE.format(name=self.name, fn="_private_api", data=extra)
        )
        if extra is None:
            extra = dict()

        query = self._sign_generator(extra)
        sig = query.pop("signature")
        query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)

        if method == "GET":
            rq = requests.get(
                self.base_url + path, params=query, headers={"X-MBX-APIKEY": self._key}
            )
        else:
            if "/withdraw/apply/" in path:
                rq = requests.post(
                    self.base_url + path, params=query, headers={"X-MBX-APIKEY": self._key}
                )
            else:
                rq = requests.post(
                    self.base_url + path, data=query, headers={"X-MBX-APIKEY": self._key}
                )

        return self._get_result(rq, path, extra, fn="_private_api")

    async def _async_private_api(self, method, path, extra=None):
        if extra is None:
            extra = dict()

        async with aiohttp.ClientSession(
            headers={"X-MBX-APIKEY": self._key}
        ) as session:
            query = self._sign_generator(extra)

            if method == "GET":
                sig = query.pop("signature")
                query = "{}&signature={}".format(urlencode(sorted(extra.items())), sig)
                rq = await session.get(self.base_url + path + "?{}".format(query))

            else:
                rq = await session.post(self.base_url + path, data=query)

            result_text = await rq.text()
            return self._get_result(result_text, path, extra, fn="_async_private_api")


if __name__ == "__main__":
    import asyncio

    bi = Binance("", "")
    bi.set_subscriber()
    bi.set_subscribe_orderbook(["BTC-XRP", "BTC_ETH"])
    while True:
        time.sleep(5)
        pk = asyncio.run(bi.get_curr_avg_orderbook())
        print(pk)
