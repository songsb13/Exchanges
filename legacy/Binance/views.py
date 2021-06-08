from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from Binance.binance import Binance
from Bithumb.bithumb import Bithumb
import requests
'''
public api는
현재 BTC 가치, 현재 한화가치, 24시간 변동률, 빗썸대비 프리미엄, 거래량
기준:빗썸

private api는
자신의 balance 가져오기
'''
###Binance Key,Gimo####
api_key = 'DxEdbh0PWqwDA2BrOJdXnagHYrH39qOED2E7I6K9PBPKkdRVhAaraAN3L3WCxuZa'
secret = 'cejp4iXz9hWtoibqi8P5ETJ0lsMxWdpRJ5dnrPpuybuPKwvdP25TDJ3sur9wRZRC'

bithumb = Bithumb('5921ef4e1e53622c4d46f827e3fcb527', '687d509dbaeaa2a01675bed46e629551')
binance_public = Binance(api_key, secret)


#123
@api_view(['GET'])
def current_data(request): #BTC ETH XRP DASH LTC ETC XMR QTUM ZEC BTG EOS
    #params = dict(request.GET)

    binance_ticker = binance_public.get_ticker()

    bithumb_data = bithumb.ticker()['data']
    bithumb_data.pop('date', None)

    bithubm_btc = bithumb_data.pop('BTC')
    bithumb_btc_krw = int(bithubm_btc['closing_price'])

    bit_dic = {}
    for bit in bithumb_data:
        bit_dic[bit] = int(bithumb_data[bit]['buy_price'])

    bin_list = []
    for data in binance_ticker:
        if not data['symbol'][-3:] == 'BTC':
            continue

        bin_list.append(data['symbol'][:-3])

    intersection = set(bithumb_data.keys()).intersection(bin_list)

    bin_dic = {}
    for coin in intersection:
        lat_coin_price = float(data['lastPrice'])
        bin_dic[coin] = {}

        bin_dic[coin]['value_btc'] = lat_coin_price
        bin_dic[coin]['value_krw'] = int(bithumb_btc_krw * lat_coin_price)
        bin_dic[coin]['price_change'] = data['priceChange']
        bin_dic[coin]['premium'] = bit_dic[coin] - bin_dic[coin]['value_krw']
        bin_dic[coin]['volume'] = data['volume']

    print(bin_dic)

    return Response(bin_dic,content_type=None)

@api_view(['POST'])
def balance(request):
    params = dict(request.POST)

    try:
        api_key = params['api_key']
        secret = params['api_secret']
    except:
        return Response({
            'result': '잘못된 형식입니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    binance = Binance(api_key, secret)

    # get balance
    balances = binance.balance()

    return Response(balances,content_type=None)
