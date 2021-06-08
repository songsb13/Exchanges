import unittest
from huobi import Huobi
import asyncio


def async_test(f):
    def wrapper(*args, **kwargs):
        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
    return wrapper


class HuobiTest(unittest.TestCase):
    @async_test
    def test_get_address(self):
        huobi = Huobi('80f255a2-d342542c-2dedc91f-db52a', '5a3d07d4-2e3f914d-1fddeea0-4fa8f')
        huobi.get_account_id()

        deposit_addrs = yield from asyncio.gather(huobi.get_deposit_addrs())
        self.assertTrue(deposit_addrs[0])
        print(deposit_addrs)

    @async_test
    def test_get_fees(self):
        huobi = Huobi('80f255a2-d342542c-2dedc91f-db52a', '5a3d07d4-2e3f914d-1fddeea0-4fa8f')
        huobi.get_account_id()

        td_fee, tx_fee = yield from asyncio.gather(huobi.get_trading_fee(), huobi.get_transaction_fee())
        self.assertTrue(td_fee[0])
        print(td_fee)
        self.assertTrue(tx_fee[0])
        print(tx_fee)

if __name__ == '__main__':
    unittest.main()
