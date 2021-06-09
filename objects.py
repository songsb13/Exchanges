class ExchangeResult(object):
    """
        Return exchange result abstract class

        success: True if success else False
        data: requested data if success is True else None
        message: result message if success is False else None
        wait_time: wait time for retry if success is False else 0
    """
    def __init__(self, success, data=None, message='', wait_time=0):

        self.success = success
        self.data = data
        self.message = message
        self.wait_time = wait_time


class DataStore(object):
    def __init__(self):
        self.channel_set = dict()
        self.activated_channels = list()
        self.orderbook_queue = dict()
        self.balance_queue = dict()
        self.candle_queue = dict()
