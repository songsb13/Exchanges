AVAILABLE_COINS = [
    'BTC_ETH', 'BTC_DASH', 'BTC_LTC', 'BTC_ETC', 'BTC_XRP', 'BTC_BCH',
    'BTC_XMR', 'BTC_ZEC', 'BTC_QTUM', 'BTC_BTG', 'BTC_EOS'
]


class Urls(object):
    BASE = 'https://api.bithumb.com'
    PAGE_BASE = 'https://www.bithumb.com'

    TICKER = '/public/ticker/{}'
    ORDER = '/trade/place'
    MARKET_BUY = '/trade/market_buy'
    MARKET_SELL = '/trade/market_sell'
    WITHDRAW = '/trade/btc_withdrawal'
    DEPOSIT_ADDRESS = '/info/wallet_address'
    ORDERBOOK = '/public/orderbook/{}'
    BALANCE = '/info/balance'
    ACCOUNT = '/info/account'
    TRANSACTION_FEE = '/customer_support/info_fee'
