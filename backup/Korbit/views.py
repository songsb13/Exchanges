from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from Korbit.korbit import Korbit
from Bithumb.bithumb import Bithumb
import requests
'''
public api는
현재 BTC 가치, 현재 한화가치, 24시간 변동률, 빗썸대비 프리미엄, 거래량
기준:빗썸

private api는
자신의 balance 가져오기
'''
###Korbit Info, Gimo###
api_key = 'VbKNWsKsRm8BgJHftXcYIPlfvm0AQULkdiIv17zbUYq7vBqn029ZxUe0rMQbu'
secret = 'zhRWiKM7feoTDIK5OUnTZ5tZuWgJklhYlfdxan80MjiXATvW4pNk8kLnwqvnu'
email = 'goodmoskito@gmail.com'
password = '!moskito235'

bithumb = Bithumb('5921ef4e1e53622c4d46f827e3fcb527', '687d509dbaeaa2a01675bed46e629551')
korbit_public = Korbit(api_key, secret, email, password)


@api_view(['GET'])
def current_data(request): #BTC ETH XRP DASH LTC ETC XMR QTUM ZEC BTG EOS
    #params = dict(request.GET)

    korbit_ticker = korbit_public.get_ticker()
    bithumb_data = bithumb.ticker()['data']

    korbit_btc_data = korbit_ticker.pop('BTC', None)
    korbit_btc_krw = int(korbit_btc_data['last'])

    intersection = set(bithumb_data.keys()).intersection(korbit_ticker.keys())

    bit_dic = {}
    for bit in intersection:
        bit_dic[bit] = int(bithumb_data[bit]['buy_price'])

    kor_dic = {}
    for coin in intersection:
        lat_coin_price = int(korbit_ticker[coin]['last'])
        kor_dic[coin] = {}

        kor_dic[coin]['value_btc'] = lat_coin_price / korbit_btc_krw
        kor_dic[coin]['value_krw'] = lat_coin_price
        kor_dic[coin]['price_change'] = korbit_ticker[coin]['change']
        kor_dic[coin]['premium'] = bit_dic[coin] - lat_coin_price
        kor_dic[coin]['volume'] = korbit_ticker[coin]['volume']

    print(kor_dic)

    return Response(kor_dic,content_type=None)

@api_view(['POST'])
def balance(request):
    params = dict(request.POST)
    try:
        api_key = params['api_key']
        secret = params['api_secret']
        email = params['email']
        password = params['password']
    except:
        return Response({
            'result': '잘못된 형식입니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    korbit = Korbit(api_key, secret,email,password)

    # get balance
    balances = korbit.get_balance()

    return Response(balances,content_type=None)
