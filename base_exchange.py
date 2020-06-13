

class BaseExchange(object):
    """
    all exchanges module should be followed BaseExchange format.
    """
    _base_url = str
    _key = str
    _secret = str

    def _public_api(self, path, extra=None):
        """
        For using public API

        :param path: URL path without Base URL, '/url/path/'
        :param extra: Parameter if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        """
        pass

    def _private_api(self, method, path, extra=None):
        """
        For using private API

        :param path: URL path without Base URL, '/url/path/'
        :param method: input required request type GET or POST
        :param extra: Parameter if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        """
        pass

    def _sign_generator(self, *args):
        """
        for using any API required signing

        *args: get parameter for signing
        :return: signed data example sha256, 512 etc..
        """
        pass

    def _symbol_localizing(self, symbol):
        """
        Matching to local use symbol, iota -> iot, bch -> bcc
        """

    def _symbol_customizing(self, symobl):
        """
        Matching to common use symbol, iot -> iota, bcc -> bch
        """

    def _currencies(self):
        """
        this function be looped up to 3 times

        :return: return symbols not customized, symbol is dependent of each exchange
        """
        pass

    def fee_count(self):
        """
        trading fee count
        :return: trading fee count, dependent of each exchange.
        example)
        korbit: krw -> btc -> alt, return 2
        upbit: btc -> alt, return 1

        """
        pass

    def get_ticker(self, market):
        """
        you can get current price this function
        this function be looped up to 3 times
        :market: symbol using in exchange
        :return: Ticker data, type is dependent of each exchange.
        """
        pass

    def get_available_coin(self):
        """
        use with _currencies
        :return: Custom symbol list ['BTC_XRP', 'BTC_LTC']
        """
        pass

    def withdraw(self, coin, amount, to_address, payment_id=None):
        """
        withdraw your coin from balance
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param to_address: ALT address
        :param payment_id: include if required
        :return: success, data, message, time
        """
        pass

    def buy(self, coin, amount, price=None):
        """
        Buy coin
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param price: type is dependent of exchange, common type is str or float. --> 0.001
        :return: success, data, message, time
        """
        pass

    def sell(self, coin, amount, price=None):
        """
        Sell coin
        :param coin: ALT symbol --> ETH, LTC ...
        :param amount: float, or str, --> 0.001
        :param price: type is dependent of exchange, common type is str or float. --> 0.001
        :return:
        """
        pass

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        """
        this function use to buy coin dependent of parameter currency_pair, alt_amount and
        calculate alt_amount withdrawn other exchange.


        :param currency_pair: BTC_ALT custom symbol.
        :param btc_amount: empty parameter
        :param alt_amount: alt amount to buy
        :param td_fee: trading fee, type is float or int
        :param tx_fee: transaction fee dict, tx_fee[customized_symbol]
        :return: success, alt amount to send subtracted fees, message, time
        """
        pass

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        """
        this function use to sell coin dependent of parameter currency_pair, btc_amount and
        calculate btc_amount be withdrawn other exchange.

        :param currency_pair: BTC_ALT custom symbol.
        :param btc_amount: empty parameter
        :param alt_amount: alt amount to sell
        :return: None
        """

    def get_precision(self, pair=None):
        """
        this function is returned minimum decimal point

        pair: BTC_XXX
        :return: success, data, message, time
        """

    async def _async_public_api(self, path, extra=None):
        """
        For using async public API

        :param method: Get or Post
        :param path: URL path without Base URL, '/url/path/'
        :param extra: Parameter if required.
        :param header: Header if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        """
        pass

    async def _async_private_api(self, method, path, extra=None):
        """
        For using async private API
        :param method: Get or Post
        :param path: URL path without Base URL, '/url/path/'
        :param extra: Parameter if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        """
        pass

    async def _get_orderbook(self, symbol):
        """
        you can get orderbook asks, bids, not customized
        this function be looped up to 3 times

        :param symbol: symbol must be exchange symbol.
        :return: orderbook, is dependent of each exchange
        """
        pass

    async def _get_deposit_addrs(self, symbol):
        """
        you can get deposit_address
        :param symbol: symbol of exchange's coin
        :return: success, address, message, time
        """

    async def _get_transaction_fee(self, symbol):
        """
        you can get transaction fee dependent of symbol
        this function be looped up to 3 times
        :return: success, data, message if you fail to get, time.
        """

    async def _get_trading_fee(self, symbol):
        """
        you can get trading fee dependent of symbol
        few exchanges are return constant value.
        this function be looped up to 3 times

        :return: success, data, message if you fail to get, time
        """
    async def _get_balance(self):
        """
        you can get balance dependent of exchange
        this function be looped up to 3 times

        :return: success, data, message if you fail to get, time
        """

    async def get_deposit_addrs(self, coin_list=None):
        """
        use with _get_deposit_addrs
        :param coin_list: None or custom symbol list --> ['BTC_XXX', ...]
        :return: exchange deposit addrs, type is have to dictonary --> {'BTC': BTCaddrs, ...}
        """
        pass

    async def get_balance(self):
        """
        use with _get_balance
        :return: user balance, type is have to dictonary --> {'BTC': float(amount), ...}
        """
        pass

    async def get_trading_fee(self):
        """
        use with _get_trading_fee
        :return: trading fee variable exchanges. type is float --> 0.01
        """

    async def get_transaction_fee(self):
        """
        use with _get_transaction_fee
        :return:  dependent of exchange, common type is have to dictonary --> {'BTC': Decimal(fee), ...}
        """

    async def get_curr_avg_orderbook(self, coin_list, btc_sum=1):
        """
        you can get orderbook average
        :param coin_list: custom symbol set [BTC_XRP, ...]
        :param btc_sum: be calculate average base on btc_sum
        :return: dict, set of custom symbol with its ask & bid average. {BTC_XRP:{asks:Decimal, bids:Decimal}, ...}
        """
        pass

    async def compare_orderbook(self, other, coins, default_btc=1):
        """
        :param other: Other exchange's compare_orderbook object
        :param coins: Custom symbol list --> [BTC_LTC, ...]
        :param default_btc: dfc
        :return: tuple, 2 different exchange orderbook & profit percent of main & sec exchanges
        """
        pass

