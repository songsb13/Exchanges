import requests
import jwt
import json
import time
from urllib.parse import urlencode
import aiohttp


class DepositStatus(object):
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    ALMOST_ACCEPTED = "almost_accepted"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    PROCESSING = "processing"


class WithdrawalStatus(object):
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    ALMOST_ACCEPTED = "almost_accepted"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    DONE = "done"
    CANCELED = "canceled"


class BaseTradeType(object):
    BUY_MARKET = "BUY_MARKET"
    BUY_LIMIT = "BUY_LIMIT"
    SELL_MARKET = "SELL_MARKET"
    SELL_LIMIT = "SELL_LIMIT"


class UpbitAPI(object):
    def __init__(self, key, secret):
        self.__key = key
        self.__secret = secret
        self.__base_url = "https://api.upbit.com/v1"

    def get_ticker(self, symbol):
        return self.__public_api("/ticker", {"markets": symbol})

    def get_all_market(self):
        return self.__public_api("/market/all")

    def get_order_history(self, uuid):
        return self.__get_private_api("/order", {"uuid": uuid})

    def get_balance(self):
        return self.__post_private_api("/accounts")

    def get_accepted_deposits(self, coin):
        return self.__get_private_api("/deposits", {"currency": coin, "state": DepositStatus.ACCEPTED})

    def market_buy(self, market, price):
        params = {
            "market": market,
            "price": price,
            "ord_type": BaseTradeType.BUY_MARKET,
        }
        return self.__post_private_api("/orders", params)

    def limit_buy(self, market, price, volume):
        params = {
            "market": market,
            "price": price,
            "volume": volume,
            "ord_type": BaseTradeType.BUY_LIMIT,
        }
        return self.__post_private_api("/orders", params)

    def market_sell(self, market, volume):
        params = {
            "market": market,
            "volume": volume,
            "ord_type": BaseTradeType.SELL_MARKET,
        }
        return self.__post_private_api("/orders", params)

    def limit_sell(self, market, price, volume):
        params = {
            "market": market,
            "price": price,
            "volume": volume,
            "ord_type": BaseTradeType.SELL_LIMIT,
        }
        return self.__post_private_api("/orders", params)

    def withdraw_coin(self, currency, address, amount):
        return self.__post_private_api("/withdraws/coin", {"currency": currency, "address": address, "amount": amount})

    def get_completed_withdraw_history(self, coin, uuid):
        return self.__get_private_api("/withdraws", {"currency": coin, "uuid": uuid, "state": WithdrawalStatus.DONE})

    def get_coin_addresses(self):
        return self.__get_private_api("/deposits/coin_addresses")

    async def withdraws_info(self, coin):
        return await self.__async_get_private_api("/withdraws/chance", {"currency": coin})

    async def get_transaction_fee(self):
        return self.__async_get_raw_api(
            url="https://api-manager.upbit.com/api/v1/kv/UPBIT_PC_COIN_DEPOSIT_AND_WITHDRAW_GUIDE"
        )

    def __public_api(self, path, extra=None):
        if extra is None:
            extra = dict()
        return requests.get(self.__base_url + path, params=extra)

    def __header_generator(self):
        payload = {
            "access_key": self.__key,
            "nonce": int(time.time() * 1000),
        }

        token = "Bearer {}".format(
            jwt.encode(
                payload,
                self.__secret,
            )
        )
        return {"Authorization": token}

    def __get_private_api(self, path, extra=None):
        extra = {"query": urlencode(extra)} if extra is not None else dict()

        response = requests.get(
            url=self.__base_url + path,
            headers=self.__header_generator(),
            params=extra
        )

        return response.json()

    def __post_private_api(self, path, extra=None):
        extra = {"query": urlencode(extra)} if extra is not None else dict()

        response = requests.post(
            url=self.__base_url + path,
            headers=self.__header_generator(),
            data=extra
        )

        return response.json()

    async def __async_get_raw_api(self, url):
        async with aiohttp.ClinetSession() as session:
            response = await session.get(url)
            return json.loads(await response.text())

    async def __async_get_private_api(self, path, extra=None):
        extra = {"query": urlencode(extra)} if extra is not None else dict()

        async with aiohttp.ClinetSession() as session:
            response = await session.get(
                url=self.__base_url + path,
                headers=self.__header_generator(),
                params=extra
            )

            return await json.loads(response.text())

    async def __async_post_private_api(self, path, extra=None):
        extra = {"query": urlencode(extra)} if extra is not None else dict()

        async with aiohttp.ClinetSession() as session:
            response = await session.post(
                url=self.__base_url + path,
                headers=self.__header_generator(),
                data=extra
            )

            return await json.loads(response.text())
