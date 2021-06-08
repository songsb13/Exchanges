import win_unicode_console
win_unicode_console.enable()

import asyncio
from Binance.binance import Binance
from Bithumb.bithumb import Bithumb
import configparser
from decimal import Decimal, ROUND_DOWN
import os
import sys
import time
from Util.pyinstaller_patch import *

cfg = configparser.ConfigParser()
cfg.read('Settings.ini')

main_logger = debugger


def find_min_balance(btc_amount, alt_amount, btc_alt, symbol):
    btc_amount = Decimal(float(btc_amount)).quantize(Decimal(10)**-4, rounding=ROUND_DOWN)
    alt_btc = Decimal(float(alt_amount) * float(btc_alt['bids'])).quantize(Decimal(10)**-4, rounding=ROUND_DOWN)
    if btc_amount < alt_btc:
        alt_amount = Decimal(float(btc_amount) / float(btc_alt['bids'])).quantize(bnc_btm_quantizer(symbol), rounding=ROUND_DOWN)
        return btc_amount, alt_amount
    else:
        alt_amount = Decimal(float(alt_amount)).quantize(bnc_btm_quantizer(symbol), rounding=ROUND_DOWN)
        return alt_btc, alt_amount


def bnc_btm_quantizer(symbol):
    binance_qtz = binance.get_step_size(symbol)
    return Decimal(10) ** -4 if binance_qtz < Decimal(10) ** -4 else binance_qtz


async def balance_and_currencies(binance, bithumb):

    loop = asyncio.get_event_loop()
    fut = [
        loop.run_in_executor(None, binance.balance),
        loop.run_in_executor(None, bithumb.balance)
    ]

    result = await asyncio.gather(*fut)

    # return result
    # main_logger.info("지갑조회 완료")

    if 'pydevd' in sys.modules:
        binance_balance = {'XRP': 10000, 'BTC': 1.0, 'DASH': 1.5, 'ETH': 10, 'BCH': 7, 'LTC': 55, 'XMR': 37, 'ETC': 262,
                           'QTUM': 298, 'ZEC': 19, 'EOS': 1000}
        bithumb_balance = {'XRP': 10000, 'BTC': 1.0, 'DASH': 1.5, 'ETH': 10, 'BCH': 7, 'LTC': 55, 'XMR': 37, 'ETC': 262,
                           'QTUM': 298, 'ZEC': 19, 'EOS': 1000}
    else:
        binance_balance, bithumb_balance = result

    main_logger.info('[Binance 잔고] {}'.format(binance_balance))
    main_logger.info('[Bithumb 잔고] {}'.format(bithumb_balance))
    currencies = list(set(bithumb_balance).intersection(binance_balance))
    # if 'EOS' in currencies:
    #     currencies.remove('EOS')
    #   EOS 이체 가능해짐
    main_logger.debug('tradable coins: {}'.format(currencies))
    temp = []
    for c in currencies:
        if c == 'BTC':
            continue
        temp.append('BTC_' + c)
    return [binance_balance, bithumb_balance, temp]


async def fees(binance, bithumb):
    loop = asyncio.get_event_loop()
    fut = [
        loop.run_in_executor(None, binance.get_trade_fee),
        loop.run_in_executor(None, bithumb.get_trading_fee),
        loop.run_in_executor(None, binance.get_transaction_fee),
        loop.run_in_executor(None, bithumb.get_transaction_fee)
    ]
    ret = await asyncio.gather(*fut)

    if not ret[2]:
        main_logger.info("Binance 이체 수수료 조회실패")
        return []

    main_logger.info("수수료 조회 성공")
    return ret


async def deposits(binance, bithumb):
    loop = asyncio.get_event_loop()

    fut = [
        loop.run_in_executor(None, binance.get_deposit_addrs),
        loop.run_in_executor(None, bithumb.get_deposit_addrs)
    ]
    ret = await asyncio.gather(*fut)

    return ret

def get_max_profit(data, balance, fee):
    binance_balance, bithumb_balance, currencies = balance
    binance_trade_fee, bithumb_trade_fee, binance_tx_fee, bithumb_tx_fee = fee
    max_profit = None
    for trade in ['m_to_s', 's_to_m']:
        for currency in currencies:
            alt = currency.split('_')[1]
            if alt not in binance_balance.keys() or not binance_balance[alt]:
                main_logger.info("[거래불가] {} Binance 입금 주소가 없습니다.".format(alt))
                continue
            if alt not in bithumb_balance.keys() or not bithumb_balance[alt]:
                main_logger.info("[거래불가] {} Bithumb 입금 주소가 없습니다.".format(alt))
                continue

            main_logger.info('[{}-{}] 예상 차익: {}%'.format(currency, trade, data[trade][currency] * 100))
            try:
                if data[trade][currency] < set_percent:
                    #   예상 차익이 %를 넘지 못하는 경우
                    # main_logger.info('[{}-{}] 예상 차익: {}%'.format(alt, trade, data[trade][currency] * 100))
                    # main_logger.info("{currency} 의 예상 차익이 {percent:,}를 넘지 않습니다.".format(currency=currency,
                    #                                                                percent=float(
                    #                                                                    cfg['Profit'][
                    #                                                                        'percent'])))
                    continue
            except ValueError:
                #   float() 이 에러가 난 경우
                main_logger.info("예상 차익 퍼센트는 실수여야만 합니다.")
                os.system("PAUSE")
                close_program(id_)
                sys.exit(1)
            real_diff = ((1 + data[trade][currency]) * ((1 - binance_trade_fee)) * ((1 - bithumb_trade_fee) ** 2)) - 1
            try:
                if trade == 'm_to_s':
                    tradable_btc, alt_amount = find_min_balance(binance_balance['BTC'], bithumb_balance[alt],
                                                                data['s_o_b'][currency], currency)
                    main_logger.info(
                        '[{}] 거래 가능: Binance {}{} / Bithumb {}BTC'.format(alt, alt_amount, alt, tradable_btc))

                    btc_profit = (tradable_btc * Decimal(real_diff)) - (
                        Decimal(binance_tx_fee[alt]) * data['m_o_b'][currency]['asks']) - Decimal(bithumb_tx_fee['BTC'])
                    main_logger.info('[{}] Binance -> Bithumb 수익: {}BTC / {}%'.format(alt, btc_profit, real_diff * 100))

                    # alt_amount로 거래할 btc를 맞춰줌, BTC를 사고 ALT를 팔기때문에 bids가격을 곱해야함
                    tradable_btc = alt_amount * data['s_o_b'][currency]['bids']
                else:
                    tradable_btc, alt_amount = find_min_balance(bithumb_balance['BTC'], binance_balance[alt],
                                                                data['m_o_b'][currency], currency)
                    main_logger.info(
                        '[{}] 거래 가능: Bithumb {}{} / Binance {}BTC'.format(alt, alt_amount, alt, tradable_btc))

                    btc_profit = (tradable_btc * Decimal(real_diff)) - (
                            Decimal(bithumb_tx_fee[alt]) * data['s_o_b'][currency][
                        'asks']) - Decimal(binance_tx_fee['BTC'])
                    main_logger.info('[{}] Bithumb -> Binance 수익: {}BTC / {}%'.format(alt, btc_profit, real_diff * 100))

                    # alt_amount로 거래할 btc를 맞춰줌, ALT를 사고 BTC를 팔기때문에 asks가격을 곱해야함
                    tradable_btc = alt_amount * data['s_o_b'][currency]['asks']

                tradable_btc = tradable_btc.quantize(Decimal(10)**-4, rounding=ROUND_DOWN)
                main_logger.debug('actual trading btc: {}'.format(tradable_btc))
                main_logger.debug('tradable bids/asks: bithumb: {} binance: {}'.format(data['s_o_b'][currency],
                                                                                       data['m_o_b'][currency]))
            except:
                debugger.exception("FATAL")

            if btc_profit <= min_btc:
                debugger.info('[{}] 수익이 {} 보다 낮아 거래하지 않습니다.'.format(alt, min_btc))
                continue

            if max_profit is None and (tradable_btc != 0 or alt_amount != 0):
                max_profit = [btc_profit, tradable_btc, alt_amount, currency, trade]
            elif max_profit is None:
                pass
            elif max_profit[0] < btc_profit:
                max_profit = [btc_profit, tradable_btc, alt_amount, currency, trade]
            #  최고 이익일 경우, 저장함
    return max_profit

def trade(binance, bithumb, max_profit, deposit_addrs, fee):
    """
    :param binance:
    :param bithumb:
    :param max_profit:
    :param bithumb_deposit_addrs:
    :return:
    """
    main_logger.info("최대 이윤 계산결과가 설정한 지정 BTC 보다 높습니다.")
    main_logger.info("거래를 시작합니다.")
    btc_profit, tradable_btc, alt_amount, currency, trade = max_profit
    binance_trade_fee, bithumb_trade_fee, binance_tx_fee, bithumb_tx_fee = fee
    if auto_withdrawal:
        binance_deposit_addrs, bithumb_deposit_addrs = deposit_addrs

    alt = currency.split('_')[1]

    if trade == 'm_to_s':
        #   Binance 에서 ALT 를 사고 Bithumb 에서 BTC 를 사서 교환함
        t = time.time()
        while True:
            if time.time() >= t + 10:
                return False
            res = binance.trade(alt+'BTC', float(alt_amount), 'buy')
            if 'code' in res.keys():
                main_logger.info("Binance: 거래에러가 발생했습니다.")
                main_logger.debug("에러내용: " + res['msg'])
            else:
                break
        main_logger.info("Binance: BTC로 {} 구입".format(alt))
        alt_amount *= (1 - Decimal(binance_trade_fee))
        alt_amount -= Decimal(binance_tx_fee[alt])
        alt_amount = alt_amount.quantize(bnc_btm_quantizer(currency), rounding=ROUND_DOWN)
        while True:
            #   이미 메인에서 거래를 했기 때문에 무조건 거래를 성공할 때 까지 진행해야만 한다
            #   나머지 경우는 메시지를 남기고 계속해서 다시 시도함
            res = bithumb.trade(False, {
                'currency': alt,
                'units': float(alt_amount)
            })
            if res['status'] == '0000':
                break
            else:
                main_logger.info("Bithumb: 판매거래 에러가 발생했습니다.")
                main_logger.debug("에러내용: " + res['message'])

        main_logger.info('Bithumb: {} 판매'.format(alt))
        while True:
            res = bithumb.trade(True, {
                'currency': 'BTC',
                'units': float(tradable_btc)
            })
            if res['status'] == '0000':
                break
            elif 'status' in res and res['status'] == '5600' and '초과' in res['message']:
                tradable_btc = (tradable_btc - (tradable_btc / 1000)).quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)
                main_logger.debug('Decrease Tradable {} to {}'.format('BTC', tradable_btc))
            else:
                main_logger.info("Bithumb: 구매거래 에러가 발생했습니다.")
                main_logger.info("에러내용: " + res['message'])
        main_logger.info('Bithumb: BTC 구매')
        send_amount = alt_amount + Decimal('{0:g}'.format(binance_tx_fee[alt]))

        if auto_withdrawal:
            while True:
                #   Binance -> Bithumb ALT 이체
                if alt == 'XRP':
                    res = binance.withdrawal_coin(alt, float(send_amount), bithumb_deposit_addrs[alt],
                                                  bithumb_deposit_addrs[alt + 'TAG'])
                else:
                    res = binance.withdrawal_coin(alt, float(send_amount), bithumb_deposit_addrs[alt])
                if 'code' in res.keys():
                    main_logger.info("Binance: {} 이체에 실패 했습니다.".format(alt))
                    main_logger.info("에러내용: " + res['msg'])
                else:
                    break
            main_logger.info('Binance -> Bithumb {alt} {unit} 만큼 이동'.format(alt=alt, unit=float(send_amount)))
            send_amount = tradable_btc + Decimal('{0:g}'.format(bithumb_tx_fee['BTC']))
            while True:
                #   Bithumb -> Binance BTC 이체
                res = bithumb.withdraw('BTC', float(send_amount), binance_deposit_addrs['BTC'])
                if res['status'] == '0000':
                    break
                else:
                    main_logger.info("Bithumb: BTC 이체에 실패 했습니다.")
                    main_logger.info("에러내용: " + res['message'])

            main_logger.info('Bithumb -> Binance BTC {unit} 만큼 이동'.format(unit=float(send_amount)))
        else:
            main_logger.info("거래가 완료되었습니다. 수동이체 후 아무키나 누르면 다시시작합니다.")
            os.system('PAUSE')
    else:
        #   Binance 에서 BTC 를 사고 Bithumb 에서 ALT 를 사서 교환함
        while True:
            #   이미 메인에서 거래를 했기 때문에 무조건 거래를 성공할 때 까지 진행해야만 한다
            #   잔고가 부족한 경우가 생긴다고 alt_amount를 줄이면 binance에서 손실이 생길것같다
            #   나머지 경우는 메시지를 남기고 계속해서 다시 시도함
            res = bithumb.trade(False, {
                'currency': 'BTC',
                'units': float(tradable_btc)
            })
            if res['status'] == '0000':
                break
            else:
                main_logger.info("Bithumb: 판매거래 에러가 발생했습니다.")
                main_logger.info("에러내용: " + res['message'])

        main_logger.info('Bithumb: BTC 판매')
        while True:
            res = bithumb.trade(True, {
                'currency': alt,
                'units': float(alt_amount)
            })
            if res['status'] == '0000':
                break
            elif 'status' in res and res['status'] == '5600' and '초과' in res['message']:
                alt_amount = (alt_amount - (alt_amount / 1000)).quantize(bnc_btm_quantizer(currency),
                                                                         rounding=ROUND_DOWN)
                main_logger.debug('Decrease Tradable {} to {}'.format(alt, alt_amount))
            else:
                main_logger.info("Bithumb: 구매거래 에러가 발생했습니다.")
                main_logger.info("에러내용: " + res['message'])
        main_logger.info('Bithumb: {} 구매'.format(alt))

        # 여기서 수수료 1회만 적용, 1회 수수료는 KRW으로 나가기 때문
        # alt_amount *= (1 - Decimal(bithumb_trade_fee))
        alt_amount *= (1 - Decimal(bithumb_trade_fee))
        alt_amount -= Decimal(bithumb_tx_fee[alt])
        alt_amount = alt_amount.quantize(bnc_btm_quantizer(currency), rounding=ROUND_DOWN)

        while True:
            res = binance.trade(alt+'BTC', float(alt_amount), 'sell')
            if 'code' in res.keys():
                main_logger.info("Binance: 거래에러가 발생했습니다.")
                main_logger.info("에러내용: " + res['msg'])
            else:
                break

        main_logger.info('Binance: {}로 BTC 구입'.format(alt))
        send_amount = alt_amount + Decimal('{0:g}'.format(bithumb_tx_fee[alt]))

        if auto_withdrawal:
            while True:
                #   Bithumb -> Binance ALT 이체
                if alt == 'XRP' or alt == 'XMR':
                    res = bithumb.withdraw(alt, float(send_amount), binance_deposit_addrs[alt],
                                           binance_deposit_addrs[alt + 'TAG'])
                else:
                    res = bithumb.withdraw(alt, float(send_amount), binance_deposit_addrs[alt])
                if res['status'] == '0000':
                    break
                else:
                    main_logger.info("Bithumb: {} 이체에 실패 했습니다.".format(alt))
                    main_logger.info("에러내용: " + res['message'])
            main_logger.info('Bithumb -> Binance {alt} {unit} 만큼 이동'.format(
                alt=alt, unit=send_amount
            ))
            send_amount = tradable_btc + Decimal('{0:g}'.format(binance_tx_fee['BTC']))
            while True:
                #   Binance -> Bithumb BTC 이체
                res = binance.withdrawal_coin('BTC', float(send_amount), bithumb_deposit_addrs['BTC'])
                if 'code' in res.keys():
                    main_logger.info("Binance: BTC 이체에 실패 했습니다.")
                    main_logger.info("에러내용: " + res['msg'])
                else:
                    break
            main_logger.info('Binance -> Bithumb BTC {} 만큼 이동'.format(send_amount))
        else:
            main_logger.info("거래가 완료되었습니다. 수동이체 후 아무키나 누르면 다시시작합니다.")
            os.system('PAUSE')

    return True


async def BinanceBithumbDiffTrader(binance, bithumb):
    if auto_withdrawal:
        main_logger.info("출금정보를 가져오는 중입니다...")
        deposit = await deposits(binance, bithumb)
        main_logger.info('출금정보 추출 완료.')
    else:
        deposit = None
    # binance_deposit_addrs, bithumb_deposit_addrs 가 온다.
    t = 0
    fee = []
    while evt.is_set():
        try:
            if time.time() >= t + 600:
                fee = await fees(binance, bithumb)
                if not fee:
                    #   실패 했을 경우 다시 요청
                    continue
                t = time.time()
            b_c = await balance_and_currencies(binance, bithumb)
            #   Binance Balance, Bithumb Balance, Common currencies
            if not b_c[2]:
                #   Intersection 결과가 비어있는 경우
                main_logger.info("거래가능한 코인이 없습니다. 잔고를 확인해 주세요")
                continue
            try:
                if b_c[0]['BTC'] > b_c[1]['BTC']:
                    default_btc = b_c[0]['BTC'] * 1.5
                else:
                    default_btc = b_c[1]['BTC'] * 1.5
            except:
                debugger.info("BTC 잔고가 없습니다. 확인해주세요.")
                continue

            debugger.debug('orderbook 호출')
            data = await binance.binance__bithumb(bithumb, default_btc, b_c[2])
            debugger.debug('orderbook 수신완료')

            # btc_profit, tradable_btc, alt_amount, currency, trade
            max_profit = get_max_profit(data, b_c, fee)
            if max_profit is None:
                main_logger.info("만족하는 조건을 찾지 못하였습니다. 조건 재검색...")
                continue
            btc_profit = max_profit[0]

            if 'pydevd' in sys.modules:
                main_logger.info("디버그 모드")
                continue

            if btc_profit > min_btc:
                #   사용자 지정 BTC 보다 많은경우
                try:
                    success = trade(binance, bithumb, max_profit, deposit, fee)
                    if not success:
                        main_logger.info("거래 대기시간이 초과되었습니다. 처음부터 다시 진행합니다.")
                        continue
                    main_logger.info("차익거래에 성공했습니다.")
                except:
                    #   trade 함수 내에서 처리하지 못한 함수가 발견한 경우
                    main_logger.exception("프로그램에 예기치 못한 문제가 발생하였습니다. 로그를 개발자에게 즉시 보내주세요")
                    os.system("PAUSE")
                    close_program(id_)
                    sys.exit(1)
            else:
                #   사용자 지정 BTC 보다 적은경우
                main_logger.info("최고 이익이 사용자 지정 BTC 보다 작아 거래하지 않습니다.")

        except:
            main_logger.exception("프로그램에 예기치 못한 문제가 발생하였습니다. 로그를 개발자에게 즉시 보내주세요")
            os.system("PAUSE")
            close_program(id_)
            sys.exit(1)

if __name__ == '__main__':
    # id_ = user_check('gosh', 'gosh1234!', 'BinanceBithumbDiffTrader')
    # id_ = user_check('aramis31', 'aramis311234!', 'BinanceBithumbDiffTrader')
    id_ = user_check('ceo_b0sCb', 'ceo_b0sCb1234!', 'BinanceBithumbDiffTrader')

    bithumb = Bithumb(cfg['Bithumb']['API key'], cfg['Bithumb']['Secret'])
    binance = Binance(cfg['Binance']['API key'], cfg['Binance']['Secret'])
    try:
        set_percent = float(cfg['Profit']['percent'])
        main_logger.debug("최소 %: {}%".format(set_percent))
        set_percent /= 100.0
        min_btc = Decimal(cfg['Profit']['minimum btc'])
        main_logger.debug("최소 btc: {}BTC".format(min_btc))
        auto_withdrawal = cfg['Withdrawal']['auto'].lower() == 'true'
        main_logger.debug("자동 출금: {}".format(auto_withdrawal))
    except:
        main_logger.info("잘못된 값이 설정되어 있습니다. 설정값을 확인해주세요")
        os.system("PAUSE")
        close_program(id_)
        sys.exit()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(BinanceBithumbDiffTrader(binance, bithumb))
    loop.close()