from django.shortcuts import render
from django_ajax.decorators import ajax
from .poloniex import Poloniex

def main(request):
    return render(request, 'Poloniex/test.html')

@ajax
def balance(request):
    # init
    secret = request.POST.get('secret')
    key = request.POST.get('key')
    poloniex = Poloniex(key, secret)

    # get balance
    balances = poloniex.get_balance()

    # get average price first from db and then poloniex api for less calculation
    avg_prices = poloniex.get_avg_price(balances)

    return avg_prices