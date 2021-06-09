from django.test import TestCase

from .poloniex import Poloniex
import time


# Create your tests here.

class PoloniexTest(TestCase):
    def setUp(self):
        self.p = Poloniex('V3SK7BOA-DN2YNUW7-H8GH5Y24-CA3UB86X',
                          '70f27533f09b2f39006eb4f41326246ffcf213a326991c15c70d3020904b722072f1aa120a0343aa0226e03f8a84f548f3cc3a68da5ce3ea56f3f7f7592a778b')

    def test_get_current_prices(self):
        tick, ids = self.p.get_current_prices()
        for _ in range(10):
            print(tick[ids['BTC_ETH']])
            time.sleep(1)

    def test_get_curr_avg_orderbook(self):
        orderbook = self.p.get_curr_avg_orderbook()
        print(orderbook)