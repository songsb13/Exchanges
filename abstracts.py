class BaseExchange(object):
    """
    all exchanges module should be followed BaseExchange format.
    """

    def _public_api(self, path, extra=None):
        """
        This function is to use the public apis.
        Args:
            path(str): The URL path without a base URL, '/url/path/'
            extra(dict, optional): Required parameter to send the API
        Returns:
            ResultObject(:obj: success, data, message, time)
                success(bool): True if successfully communicate to API server else False
                data: Data from API server, Format is depend on API Server
                message(str): Return error result message if fail to communicate to API server
                time(int): Wait time if fail to communicate to API server.
        """

    def _private_api(self, method, path, extra=None):
        """
        This function is to use the private apis
        Args:
            path(str): The URL path without a base URL, '/url/path/'
            extra(dict, optional): Required parameter to send the API
        Returns:
            ResultObject(:obj: success, data, message, time)
                success(bool): True if successfully communicate to API server else False
                data: Data from API server, Format is depend on API Server
                message(str): Return error result message if fail to communicate to API server
                time(int): Wait time if fail to communicate to API server.
        """

    def _trading_validator(self, symbol, amount):
        """
            It is trading validator for getting data integrity.
            Args:
                symbol(str): exchange's symbol
                amount(int): trading coin's amount

            Returns:
                Return a step size object if all validation logic is passed
                else return false object.

                ResultObject(:obj: success, data, message, time)
                    success(bool): True if successfully communicate to API server else False
                    data(decimal): stepped size
                    message(str): Return error result message if fail to communicate to API server
                    time(int): Wait time if fail to communicate to API server.
        """

    def _sign_generator(self, *args):
        """
            Sign generator for encrypting the parameters.
            Args:
                *args(list): parameters for signing.

            Returns:
                data(str, dict): Signed data, Or signed parameter
        """

    def fee_count(self):
        """
            Get trading fee count
            Returns:
                fee_count(int): return 2 if exchange is support only KRW market else 1
        """

    def get_ticker(self, sai_symbol):
        """
            Get ticker based on symbol
            Args:
                sai_symbol(str): customized symbol, BTC_ETH

            Returns:
                Return result object with sai_data

                ResultObject(:obj: success, data, message, time)
                    success(bool): True if successfully communicate to API server else False
                    data(decimal): ticker price based on sai_symbol
                    message(str): Return error result message if fail to communicate to API server
                    time(int): Wait time if fail to communicate to API server.
        """

    def get_order_history(self, id_, additional):
        """
            Get order history based on id_
            Args:
                id_(str): order id
                additional(dict): additional parameter
            Returns:
                Return result object with sai_data

                ResultObject(:obj: success, data, message, time)
                    success(bool): True if successfully communicate to API server else False
                    data(dict): get order history data
                        sai_status(str): order's status
                        sai_average_price(decimal): order's average price
                        sai_amount(decimal): order's trading amount
                    message(str): Return error result message if fail to communicate to API server
                    time(int): Wait time if fail to communicate to API server.
        """

    def get_deposit_history(self, coin):
        """
            Get deposit history based on coin
            Args:
                coin(str): ALT coin name
            Returns:
                Return result object with sai_data

                ResultObject(:obj: success, data, message, time)
                    success(bool): True if successfully communicate to API server else False
                    data(dict): get deposit history data
                        sai_deposit_amount(decimal): history's deposit amount
                        sai_coin(str): coin name
                    message(str): Return error result message if fail to communicate to API server
                    time(int): Wait time if fail to communicate to API server.
        """

    def get_available_symbols(self):
        """
            Get exchange's available symbols

            Returns:
                Return result object with sai_data

                ResultObject(:obj: success, data, message, time)
                    success(bool): True if successfully communicate to API server else False
                    sai_symbols(list): [BTC_XRP, BTC_ETH, ...]
                    message(str): Return error result message if fail to communicate to API server
                    time(int): Wait time if fail to communicate to API server.
        """

    def set_subscribe_candle(self, symbol):
        """
            Execute subscribe candle.
            Args:
                symbol(str, list): It can be inserted [BTC-XRP, BTC-ETH] or 'BTC-XRP'
            Returns:
                True
        """

    def set_subscribe_orderbook(self, symbol):
        """
            Execute subscribe orderbook.
            Args:
                symbol(str, list): It can be inserted [BTC-XRP, BTC-ETH] or 'BTC-XRP'
            Returns:
                True
        """

    def get_orderbook(self):
        """
            Get exchange's orderbooks that depend on orderbooks's queue in data_store

            Returns:
                get_orderbook is always return success=True, message=str()
                Return result object with orderbook ResultObject(:obj: success, data, message, time)
                    success(bool): True if successfully communicate to API server else False
                    orderbook_data(dict): {'BTC_ETH': [{'bids': 0.3, 'asks': 0.35}, ..], 'BTC_XRP': ...}
        """

    def get_candle(self, sai_symbol):
        """
            Get exchange's candle that depend on candle's queue in data_store
            Args:
                sai_symbol(str): sai_symbol, BTC_XRP
            Returns:
                get_candle is always return success=True, message=str()
                Return result object with orderbook ResultObject(:obj: success, data, message, time)
                    success(bool): True if successfully communicate to API server else False
                    candle_data(dict): {'BTC_ETH': [{
                                            'high': 0.3,
                                            'low': 0.35,
                                            'close': 0.35,
                                            'open': 0.35,
                                            'timestamp': 0.35,
                                            amount: 0.003
                                        }, ..], 'BTC_XRP': ...}
        """

    def withdraw(self, coin, amount, to_address, payment_id=None):
        """
            Execute withdraw

            Args:
                coin(str): withdraw coin
                amount(decimal): withdraw amount
                to_address(str): destination address
                payment_id(str): destination tag or payment id if it is need.

            Returns:
                Return result object with sai_id
                    success(bool): True if successfully communicate to API server else False
                    sai_id(str): withdraw id
                    message(str): Return error result message if fail to communicate to API server
                    time(int): Wait time if fail to communicate to API server.

        """

    def buy(self, sai_symbol, trade_type, amount=None, price=None):
        """
            Execute Buy

            Args:
                sai_symbol(str): sai_symbol, BTC_XRP
                trade_type(str): trade_type, it is depend on BaseTradeType.
                amount(none, decimal): buy amount
                price(none, decimal): buy price

            Returns:
                Return result object with sai_id
                    success(bool): True if successfully communicate to API server else False
                    data(dict): get executed info with sai_data
                        sai_average_price(decimal): executed average_price
                        sai_amount(decimal): executed amount
                        sai_order_id(str): order id
                    message(str): Return error result message if fail to communicate to API server
                    time(int): Wait time if fail to communicate to API server.
        """

    def sell(self, sai_symbol, amount, trade_type, price=None):
        """
            Execute Sell

            Args:
                sai_symbol(str): sai_symbol, BTC_XRP
                trade_type(str): trade_type, it is depend on BaseTradeType.
                amount(none, decimal): buy amount
                price(none, decimal): buy price

            Returns:
                Return result object with sai_id
                    success(bool): True if successfully communicate to API server else False
                    data(dict): get executed info with sai_data
                        sai_average_price(decimal): executed average_price
                        sai_amount(decimal): executed amount
                        sai_order_id(str): order id
                    message(str): Return error result message if fail to communicate to API server
                    time(int): Wait time if fail to communicate to API server.
        """

    def base_to_alt(self, coin, alt_amount, td_fee, tx_fee):
        """
            It is formula function that calculate withdraw amount.
            Args:
                coin: coin
                alt_amount: alt_amount
                td_fee: coin's trading_fee
                tx_fee: coin's transaction_fee
        """

    def get_precision(self, sai_symbol=None):
        """
        this function is returned minimum decimal point

        :param sai_symbol: BTC_XXX
        :return: success, data, message, time
        """

    async def _async_public_api(self, path, extra=None):
        """
        For using async public API

        :param path: URL path without Base URL, '/url/path/'
        :param extra: Parameter if required.
        :return:
        return 4 format
        1. success: True if status is 200 else False
        2. data: response data
        3. message: if success is False, logging with this message.
        4. time: if success is False, will be sleep this time.
        """

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

    async def _get_deposit_addrs(self, symbol):
        """
        you can get deposit_address
        :param symbol: symbol of exchange's coin
        :return: success, address, message, time
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

    async def get_balance(self):
        """
        use with _get_balance
        :return: user balance, type is have to dictonary --> {'BTC': float(amount), ...}
        """

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

    async def compare_orderbook(self, other, coins, default_btc=1):
        """
        :param other: Other exchange's compare_orderbook object
        :param coins: Custom symbol list --> [BTC_LTC, ...]
        :param default_btc: dfc
        :return: tuple, 2 different exchange orderbook & profit percent of main & sec exchanges
        """
