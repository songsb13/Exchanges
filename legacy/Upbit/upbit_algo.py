import requests


class Upbit:
    def __init__(self):

        self.endpoint = "https://api.upbit.com/v1"

    def request(self,path,params=None):
        if params is None:
            params = {}

        req = requests.get(self.endpoint + path, params=params)

        if req.status_code != 200:
            req = {'err-msg': '서버가 정상적으로 응답되지 않았습니다. StatusCode=[{}]'.format(req.status_code)}

            return req

        try:
            req = req.json()

        except Exception as e:
            req = {'err-msg': e}

        return req

    def get_available_coin(self):
        path = '/market/all'

        data = self.request(path)

        ret_list = []

        for info in data:
            ret_list.append(info['market'])

        if 'err-msg' in data:
            return False, 'fail', data['err-msg'], 1

        else:
            return True, ret_list, '', 0

    def get_candle(self, coin, unit, count):
        # 1, 3, 5, 15, 10, 30, 60, 240 분이 가능함.

        path = '/candles/minutes/' + str(unit)
        coin = coin.replace('_', '-')
        params = {'market': coin, 'count': count}

        data = self.request(path, params)

        if 'err-msg' in data:
            return False, 'Fail', data['err-msg'], 1

        data = data[::-1]

        coin_history = {}
        coin_history['open'] = []
        coin_history['high'] = []
        coin_history['low'] = []
        coin_history['close'] = []
        coin_history['volume'] = []
        coin_history['timestamp'] = []

        for info in data:   # 리스트가 늘어날 수도?
            coin_history['open'].append(info['opening_price'])
            coin_history['high'].append(info['high_price'])
            coin_history['low'].append(info['low_price'])
            coin_history['close'].append(info['trade_price'])
            coin_history['volume'].append(info['candle_acc_trade_volume'])
            coin_history['timestamp'].append(info['candle_date_time_kst'])

        return True, coin_history, '', 0