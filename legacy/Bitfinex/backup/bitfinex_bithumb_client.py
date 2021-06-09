from Bitfinex.bitfinex import Bitfinex
from Bithumb.bithumb import Bithumb
import asyncio
from Util.pyinstaller_patch import *
import configparser
from decimal import Decimal, ROUND_DOWN
import sys
import win_unicode_console

win_unicode_console.enable()

cfg = configparser.ConfigParser()
cfg.read('Settings.ini')

debug = cfg['Debug']['set'].lower()
debugger.debug('디버그 모드: {}'.format(debug))


def find_min_balance(btc_amount, alt_amount, btc_alt):
    btc_amount = Decimal(float(btc_amount)).quantize(Decimal(10)**-4, rounding=ROUND_DOWN)
    alt_btc = Decimal(float(alt_amount) * float(btc_alt)).quantize(Decimal(10)**-4, rounding=ROUND_DOWN)
    if btc_amount < alt_btc:
        alt_amount = Decimal(float(btc_amount) / float(btc_alt)).quantize(Decimal(10)**-4, rounding=ROUND_DOWN)
        return btc_amount, alt_amount
    else:
        alt_amount = Decimal(float(alt_amount)).quantize(Decimal(10)**-4, rounding=ROUND_DOWN)
        return alt_btc, alt_amount


def main():
    bitfinex_td_fee_last_retrieve_time = 0
    bitfinex_tx_fee_last_retrieve_time = 0
    bithumb_tx_fee_last_retrieve_time = 0
    while evt.is_set():
        bitfinex_balance = bitfinex.get_balance()
        if 'pydevd' in sys.modules:
            bitfinex_balance.update({'XRP': 10000, 'BTC': 10.0, 'DASH': 1.5, 'ETH': 10, 'BCH': 7, 'LTC': 55, 'XMR': 37,
                                     'ETC': 262, 'QTUM': 298, 'ZEC': 19, 'EOS': 1000})
        if time.time() > bitfinex_tx_fee_last_retrieve_time + 600:
            bitfinex_tx_fee, bitfinex_tx_fee_last_retrieve_time = bitfinex.get_transaction_fee()
        if time.time() > bitfinex_td_fee_last_retrieve_time + 600:
            bitfinex_td_fee, last_bitfinex_td_fee_retrieve_time = bitfinex.get_trading_fee()
        debugger.info('[Bitfinex 잔고] {}'.format(bitfinex_balance))

        bithumb_balance = bithumb.get_balance()
        if 'pydevd' in sys.modules:
            bithumb_balance.update({'XRP': 10000, 'BTC': 1.0, 'DASH': 1.5, 'ETH': 10, 'BCH': 7, 'LTC': 55, 'XMR': 37,
                                    'ETC': 262, 'QTUM': 298, 'ZEC': 19, 'EOS': 1000})
        if time.time() > bithumb_tx_fee_last_retrieve_time + 600:
            bithumb_tx_fee, bithumb_tx_fee_last_retrieve_time = bithumb.get_transaction_fee()
            if 'EOS' not in bithumb_tx_fee:
                bithumb_tx_fee.update({'EOS': Decimal(0.1)})
            bithumb_td_fee = bithumb.get_trading_fee()
        debugger.info('[Bithumb 잔고] {}'.format(bithumb_balance))

        intersecting_coins = list(set(bithumb_balance).intersection(bitfinex_balance))
        if 'BTG' in intersecting_coins:
            intersecting_coins.remove('BTG')
        debugger.debug('tradable coins: {}'.format(intersecting_coins))

        if intersecting_coins == []:
            debugger.info("거래 가능한 알트코인이 없습니다. 잔고를 확인해 주세요")
            continue

        try:
            if bitfinex_balance['BTC'] > bithumb_balance['BTC']:
                default_btc = bitfinex_balance['BTC'] * 1.5
            else:
                default_btc = bithumb_balance['BTC'] * 1.5
        except:
            debugger.info("BTC 잔고가 없습니다. 확인해주세요.")
            continue

        bitfinex_avg_orderbook, bithumb_avg_orderbook, diff = loop.run_until_complete(
            bitfinex.bitfinex__other(bithumb, intersecting_coins, default_btc))

        max_profit = None
        for key in diff['m_to_s']:
            alt = key.split('_')[1].upper()
            if alt not in intersecting_coins:
                debugger.info('[거래불가] {} 잔고 부족합니다.'.format(alt))
                continue
            if alt not in bitfinex_deposit_addrs:
                debugger.info('[거래불가] {} Bitfinex 입금 주소가 없습니다.'.format(alt))
                continue
            if alt not in bithumb_deposit_addrs:
                debugger.info('[거래불가] {} Bithumb 입금 주소가 없습니다.'.format(alt))
                continue
            for t in ['m_to_s', 's_to_m']:
                debugger.info('[{}-{}] 예상 차익: {}%'.format(key, t, diff[t][key] * 100))
                if diff[t][key] >= set_percent:
                    # buy from bitfinex -> sell to bithumb
                    if t == 'm_to_s':
                        # real_diff = ((Expected Profit + 1) *
                        # (1 - Sub Exchange Trading Fee) ** (Sub Exchange Trading Fee Charging Count))
                        # -
                        # ((1 + Main Exchange Trading Fee) ** (Main Exchange Trading Fee Charging Count)
                        real_diff = ((diff[t][key] + 1) * ((1 - float(bithumb_td_fee)) ** 2)) - (1 + float(bitfinex_td_fee))

                        tradable_btc, alt_amount = find_min_balance(bitfinex_balance['BTC'], bithumb_balance[alt],
                                                                    float(bithumb_avg_orderbook[key]['bids']))

                        debugger.info(
                            '[{}] 거래 가능: Bitfinex {}{} / Bithumb {}BTC'.format(alt, alt_amount, alt, tradable_btc))
                        btc_profit = (tradable_btc * Decimal(real_diff)) - bithumb_tx_fee['BTC'] - (
                            bitfinex_tx_fee[alt] * Decimal(bitfinex_avg_orderbook[key]['asks']))

                        debugger.info('[{}] Bitfinex -> Bithumb 수익: {}BTC / {}%'.format(alt, btc_profit, real_diff * 100))
                    # buy from bithumb -> sell to bitfinex
                    else:
                        # real_diff = ((1 - Main Exchange Trading Fee) ** (Main Exchange Trading Fee Charging Count)
                        # -
                        # ((1 - Expected Profit) *
                        # (1 + Sub Exchange Trading Fee) ** (Sub Exchange Trading Fee Charging Count))
                        real_diff = (1 - float(bitfinex_td_fee)) - ((1 - diff[t][key]) * ((1 + float(bithumb_td_fee)) ** 2))

                        tradable_btc, alt_amount = find_min_balance(bithumb_balance['BTC'], bitfinex_balance[alt],
                                                                    float(bitfinex_avg_orderbook[key]['bids']))

                        debugger.info(
                            '[{}] 거래 가능: Bitfinex {}BTC / Bithumb {}{}'.format(alt, tradable_btc, alt_amount, alt))
                        btc_profit = (tradable_btc * Decimal(real_diff)) - bitfinex_tx_fee['BTC'] - (
                            bithumb_tx_fee[alt] * Decimal(bithumb_avg_orderbook[key]['asks']))

                        debugger.info('[{}] Bithumb -> Bitfinex 수익: {}BTC / {}%'.format(alt, btc_profit, real_diff * 100))

                    if btc_profit <= min_btc:
                        debugger.info('[{}] 수익이 {} 보다 낮아 거래하지 않습니다.'.format(alt, min_btc))
                        continue

                    if max_profit is None:
                        max_profit = [btc_profit, tradable_btc, alt_amount, key, t]
                    elif max_profit[0] < btc_profit:
                        max_profit = [btc_profit, tradable_btc, alt_amount, key, t]

                    debugger.debug('[{}] tradable amount: {}'.format(alt, tradable_btc))

        if max_profit is None:
            debugger.info('만족하는 조건이 없으므로 거래하지 않습니다.')
            time.sleep(5)
            continue

        if debug == 'true':
            debugger.info('디버그 모드이므로 거래하지 않습니다.')
            continue

        debugger.info('********************')
        debugger.info('거래를 시작합니다. 프로그램을 강제로 종료하지 말아주세요.')
        debugger.info('********************')
        # max_profit = [btc_profit, tradable_btc, alt_amount, key, t]
        btc_profit = max_profit[0]
        tradable_btc = max_profit[1]
        alt_amount = max_profit[2]
        key = max_profit[3]
        t = max_profit[4]
        alt = key.split('_')[1].upper()
        # buy from bitfinex -> sell to bithumb
        if t == 'm_to_s':
            res = bitfinex.buy(key, alt_amount)
            debugger.debug(res)
            alt_amount *= (1 - bitfinex_td_fee)
            alt_amount -= bitfinex_tx_fee[alt]
            alt_amount = alt_amount.quantize(Decimal(10)**-4, rounding=ROUND_DOWN)
            while True:
                res = bithumb.trade(buy=False, extra_params={'currency': alt, 'units': float(alt_amount)})
                if 'status' in res and res['status'] == '5600' and (
                                '잠시 후' in res['message'] or 'try again' in res['message']):
                    debugger.info(res['message'])
                elif 'status' in res and res['status'] == '5100' and 'Bad' in res['message']:
                    debugger.info(res['message'])
                elif res['status'] == '0000':
                    break
                else:
                    debugger.debug(res)

                time.sleep(5)

            while True:
                res = bithumb.trade(buy=True, extra_params={'currency': 'BTC', 'units': float(tradable_btc)})
                if 'status' in res and res['status'] == '5600' and (
                                '잠시 후' in res['message'] or 'try again' in res['message']):
                    debugger.info(res['message'])
                elif 'status' in res and res['status'] == '5600' and '초과' in res['message']:
                    tradable_btc = tradable_btc - Decimal(0.0001).quantize(Decimal(10)**-4)
                    debugger.debug('Decrease Tradable BTC to {}'.format(tradable_btc))
                elif 'status' in res and res['status'] == '5100' and 'Bad' in res['message']:
                    debugger.info(res['message'])
                elif res['status'] == '0000':
                    break
                else:
                    debugger.debug(res)

                time.sleep(5)

            send_amount = alt_amount + bitfinex_tx_fee[alt]
            if alt == 'XRP':
                debugger.debug('bitfinex withdraw: {} {} {} {}'.format(alt, send_amount, bithumb_deposit_addrs[alt],
                                                                       bithumb_deposit_addrs['XRPTAG']))
                res = bitfinex.withdraw(alt, send_amount, bithumb_deposit_addrs[alt], bithumb_deposit_addrs['XRPTAG'])
            else:
                debugger.debug('bitfinex withdraw: {} {} {}'.format(alt, send_amount, bithumb_deposit_addrs[alt]))
                res = bitfinex.withdraw(alt, send_amount, bithumb_deposit_addrs[alt])
            debugger.debug('bitfinex withdraw Done: {}'.format(res))

            send_amount = tradable_btc + bithumb_tx_fee['BTC']
            debugger.debug('bithumb withdraw: BTC {} {}'.format(send_amount, bitfinex_deposit_addrs['BTC']))
            res = bithumb.withdraw('BTC', send_amount, bitfinex_deposit_addrs['BTC'])
            debugger.debug('bithumb withdraw Done: {}'.format(res))
        # buy from bithumb -> sell to bitfinex
        else:
            while True:
                res = bithumb.trade(buy=False, extra_params={'currency': 'BTC', 'units': float(tradable_btc)})
                if 'status' in res and res['status'] == '5600' and (
                                '잠시 후' in res['message'] or 'try again' in res['message']):
                    debugger.info(res['message'])
                elif 'status' in res and res['status'] == '5100' and 'Bad' in res['message']:
                    debugger.info(res['message'])
                elif res['status'] == '0000':
                    break
                else:
                    debugger.debug(res)

                time.sleep(5)

            while True:
                res = bithumb.trade(buy=True, extra_params={'currency': alt, 'units': float(alt_amount)})
                if 'status' in res and res['status'] == '5600' and (
                                '잠시 후' in res['message'] or 'try again' in res['message']):
                    debugger.info(res['message'])
                elif 'status' in res and res['status'] == '5600' and '초과' in res['message']:
                    alt_amount = alt_amount - (bithumb_tx_fee[alt] / 10)
                    debugger.debug('Decrease Tradable {} to {}'.format(alt, alt_amount))
                elif 'status' in res and res['status'] == '5100' and 'Bad' in res['message']:
                    debugger.info(res['message'])
                elif res['status'] == '0000':
                    break
                else:
                    debugger.debug(res)

                time.sleep(5)

            alt_amount *= (1 - bithumb_td_fee)
            alt_amount *= (1 - bithumb_td_fee)
            alt_amount -= bithumb_tx_fee[alt]
            alt_amount = alt_amount.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

            res = bitfinex.sell(key, alt_amount)
            debugger.debug(res)

            send_amount = alt_amount + bithumb_tx_fee[alt]
            if alt == 'XRP':
                debugger.debug('bithumb withdraw: {} {} {} {}'.format(alt, send_amount, bitfinex_deposit_addrs[alt],
                                                                      bitfinex_deposit_addrs['XRPTAG']))
                res = bithumb.withdraw(alt, send_amount, bitfinex_deposit_addrs[alt], bitfinex_deposit_addrs['XRPTAG'])
            elif alt == 'XMR':
                debugger.debug('bithumb withdraw: {} {} {} {}'.format(alt, send_amount, bitfinex_deposit_addrs[alt],
                                                                      bitfinex_deposit_addrs['XMRPaymentId']))
                res = bithumb.withdraw(alt, send_amount, bitfinex_deposit_addrs[alt],
                                       bitfinex_deposit_addrs['XMRPaymentId'])
            else:
                debugger.debug('bithumb withdraw: {} {} {}'.format(alt, send_amount, bitfinex_deposit_addrs[alt]))
                res = bithumb.withdraw(alt, send_amount, bitfinex_deposit_addrs[alt])
            debugger.debug('bithumb withdraw Done: {}'.format(res))

            send_amount = tradable_btc + bitfinex_tx_fee['BTC']
            debugger.debug('bitfinex withdraw: BTC {} {}'.format(send_amount, bithumb_deposit_addrs['BTC']))
            res = bitfinex.withdraw('BTC', send_amount, bithumb_deposit_addrs['BTC'])
            debugger.debug('bitfinex withdraw Done: {}'.format(res))

        debugger.info('********************')
        debugger.info('거래를 완료하였습니다.')
        debugger.info('********************')


if __name__ == '__main__':

    try:
        bitfinex = Bitfinex(cfg['Bitfinex']['API key'], cfg['Bitfinex']['Secret'])
        bithumb = Bithumb(cfg['Bithumb']['API key'], cfg['Bithumb']['Secret'])

        debugger.info("출금정보를 가져오는 중입니다...")
        bitfinex_deposit_addrs = bitfinex.get_deposit_addrs()
        # bitfinex_deposit_addrs.update({
        #     'BTG': cfg['Bitfinex']['BTG Address'],
        #     'DASH': cfg['Bitfinex']['DASH Address'],
        #     'EOS': cfg['Bitfinex']['EOS Address'],
        #     'QTUM': cfg['Bitfinex']['QTUM Address'],
        #     'XRP': cfg['Bitfinex']['XRP Address'],
        #     'XRPTAG': cfg['Bitfinex']['XRP Tag']
        # })
        bithumb_deposit_addrs = bithumb.get_deposit_addrs()
        debugger.info('출금정보 추출 완료.')

        loop = asyncio.get_event_loop()
        set_percent = float(cfg['Profit']['percent'])
        debugger.debug("최소 %: {}%".format(set_percent))
        set_percent /= 100.0
        min_btc = Decimal(cfg['Profit']['minimum btc'])
        debugger.debug("최소 btc: {}BTC".format(min_btc))

        main()

        loop.close()
    except:
        debugger.exception('FATAL')
        debugger.info("로그를 개발자에게 보내주세요!")
    finally:
        close_program(id_)

    debugger.debug('완료.\n\n\n\n\n')
