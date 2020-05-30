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


# todo BaseExchange 와 다른 파일에 분리해야 할지 생각
class DataStore(object):
    def __init__(self):
        self.orderbook_raw_data = None
        self.balance_raw_data = None
        self.candle_raw_data = None
