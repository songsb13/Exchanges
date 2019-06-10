from pyinstaller_patch import *
import base64
import ssl
import json
import hmac
import websocket
from selenium.common.exceptions import *
from selenium import webdriver
from telegram.error import TimedOut
import re
from threading import Thread
import asyncio
import aiohttp
from queue import Queue
from decimal import Decimal, ROUND_DOWN

DRIVER_PATH = os.path.join(sys._MEIPASS, 'chromedriver.exe')


class Upbit:
    def __init__(self, username, password, token, chat_id):
        self.token = token
        self.chat_id = chat_id

        self.username = None
        self.password = None

        self.ws = None
        self.order_book = None
        self.ticker = None
        self.updater = None
        self.message = Queue()
        self.driver = None

        self.client = None
        self.secret = None
        self.bot = None

    def __del__(self):
        self.socket_close()
        self.off()

    def get_message(self):
        try:
            t = time.time()
            updates = self.bot.get_updates()
            if updates:
                update_id = updates[-1].update_id
            else:
                update_id = None
            while time.time() <= t + 170:
                try:
                    u = self.bot.get_updates()[-1]
                except TimedOut:
                    continue
                if u.update_id != update_id and str(u.message.chat_id) == str(self.chat_id):
                    txt = u.message.text
                    debugger.info("{} 입력 받음".format(txt))
                    return txt
                time.sleep(1)
            return False
        except:
            debugger.exception("텔레그램 에러발생")
            return False

    def socket_close(self):
        if self.ws:
            try:
                self.ws.close()
            except:
                pass

    def chrome(self, headless=False, incognito=True, wait_sec=15):
        if not self.driver:
            opt = webdriver.ChromeOptions()
            opt.add_argument('--silent')
            opt.add_argument('--disable-infobars')
            if headless:
                opt.add_argument('--headless')
            if incognito:
                opt.add_argument('--incognito')

            self.driver = webdriver.Chrome(DRIVER_PATH, chrome_options=opt)
            self.driver.implicitly_wait(wait_sec)

    def off(self):
        if self.driver:
            try:
                self.driver.quit()
            except WebDriverException:
                debugger.exception("웹브라우저 종료 실패")

            self.driver = None

    def sign_in(self, username, password):
        self.driver.get('https://upbit.com/signin')

        while True:
            try:
                kakao_button = self.driver.find_element_by_class_name('btnKakao')
                break
            except NoSuchElementException:
                debugger.info("카카오 로그인 버튼 찾기 실패!!")
                return False, '', "페이지 로딩에 실패하였습니다...", 2
        chk_box = self.driver.find_element_by_css_selector('.chkBox > a')
        self.driver.execute_script("arguments[0].click();", chk_box)
        time.sleep(1)
        kakao_button.click()
        win_handle = self.driver.window_handles  # 새로나온 윈도우 창으로 포커스
        idx = -1
        while True:
            try:
                self.driver.switch_to.window(win_handle[idx])

                self.driver.execute_script("arguments[0].click();", self.driver.find_element_by_id('staySignedIn'))
                self.driver.find_element_by_id('loginEmail').send_keys(username.strip())
                time.sleep(.5)
                self.driver.find_element_by_id('loginPw').send_keys(password.strip() + '\n')
                break

            except NoSuchWindowException:
                idx -= 1
            except NoSuchElementException:
                idx -= 1

        time.sleep(2)
        self.driver.implicitly_wait(2)
        try:
            em = self.driver.find_element_by_id('error-message')  # 아이디/비밀번호 잘못된 입력
            debugger.info("아이디/비밀번호 잘못된 입력.")
            return False, ' ', "아이디/비밀번호 잘못된 입력.", 0
        except Exception as e:
            debugger.info("아이디/비밀번호 로그인 성공.")

        try:
            self.driver.switch_to.window(win_handle[0])
        except:
            print('')

        try:  # 인증검증 버튼이 있을경우
            time.sleep(1)
            _input_vrf = self.driver.find_element_by_xpath('//span[@class="btnB time"]/input')
            debugger.info("카카오 인증번호 대기...")
            while True:
                time.sleep(1)
                self.bot.sendMessage(self.chat_id, '카카오 인증번호를 입력해주세요: ')
                code = self.get_message()
                if not code:
                    self.bot.send_message(self.chat_id, '인증번호 입력시간을 초과했습니다.')
                    debugger.info("인증번호 입력시간을 초과했습니다.")
                    return False, ' ', "인증번호 입력시간을 초과했습니다.", 0
                _input_vrf.clear()
                _input_vrf.send_keys(code.strip() + '\n')

                if not self.pop_up_check():  # 팝업창이 뜨면 인증실패
                    debugger.info("인증성공.")
                    try:
                        self.updater.stop()
                    except:
                        pass
                    break
                else:
                    return False, '', "인증실패. 재시도 합니다.", 0
        except:  # 인증번호 받는 페이지가 없을수도있음 ex)2번째 인증을 안할경우
            debugger.debug("인증페이지 없음으로 넘어감..")

        self.driver.implicitly_wait(5)
        self.username = username
        self.password = password

        cookies = self.driver.get_cookie('tokens')['value']

        return True, cookies, '', 0

    def pop_up_check(self):
        debugger.debug("pop_up_check.")

        try:
            popup = self.driver.find_element_by_class_name('popup01')  # 인증번호 잘못된 입력시 나오는 팝업
            t = popup.text
            debugger.debug(t)
            self.driver.find_element_by_xpath('//*[@class="popup01"]/article/span/a').click()
            return True  # 팝업뜨면 true

        except:
            debugger.debug("pop_up_check - Fail.")
            return False

    def decrypt_token(self, token):
        tk = json.loads(token)
        payload = tk['accessToken'].split('.')
        pair = json.loads(base64.b64decode(payload[1] + '==').decode())['api']
        self.client = pair['access_key']
        self.secret = pair['secret_key']

        debugger.info("JWT Client: {}".format(self.client))
        debugger.info("JWT Secret: {}".format(self.secret))

    def jwt(self):
        if not self.client or not self.secret:
            return False

        sig1 = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        sig2 = base64.b64encode(
            json.dumps({'access_key': self.client, 'nonce': int(time.time() * 1000)}).replace(' ',
                                                                                              '').encode()).decode()
        sig2 = re.sub("=+", "", sig2.replace('/', '_').replace('+', '-'))
        signature = base64.b64encode(
            hmac.new(self.secret.encode(), (sig1 + '.' + sig2).encode(), hashlib.sha256).digest()).decode()

        signature = re.sub("=+", "", signature.replace('/', '_').replace('+', '-'))

        ret = sig1 + "." + sig2 + "." + signature

        return ret

    def withdraw(self, coin, amount, to_address, payment_id=None):
        token = self.jwt()

        headers = {
            'Authorization': 'Bearer ' + token
        }
        url = 'https://ccx.upbit.com/api/v1/withdraws/coin/request_two_factor'
        data = {
            'currency': coin,
            'amount': '{}'.format(amount),
            'address': to_address
        }
        if payment_id:
            data['address'] += '?dt=' + payment_id
        try:
            r = requests.post(url, headers=headers, json=data)
            dt = r.json()
            if 'error' in dt.keys():
                return False, '', dt['error']['message'], 5
        except Exception as e:
            return False, '', str(e), 5

        t = time.time()
        while time.time() < t + 180:
            try:
                self.bot.sendMessage(self.chat_id, '출금 인증번호를 입력해주세요: ')
                code = self.get_message()
                if not code:
                    self.bot.send_message(self.chat_id, '인증번호 입력시간을 초과했습니다.')
                    debugger.info("인증번호 입력시간을 초과했습니다.")
                    return False, ' ', "인증번호 입력시간을 초과했습니다.", 0
                else:
                    break
            except TimedOut:
                time.sleep(1)
                continue
        else:
            self.bot.send_message(self.chat_id, '인증번호 입력시간을 초과했습니다.')
            debugger.info("인증번호 입력시간을 초과했습니다.")
            return False, ' ', "인증번호 입력시간을 초과했습니다.", 0
        data.update({
            'tx_id': dt['tx_id'],
            'check_two_factor': True,
            'otp': code,
            'withdraw_confirmation': True
        })
        url = 'https://ccx.upbit.com/api/v1/withdraws/coin/request'
        try:
            r = requests.post(url, headers=headers, data=data)
            if r.status_code >= 400:
                return False, '', r.json(), 5
            else:
                return True, r.json(), '', 0
        except Exception as e:
            return False, '', str(e), 5

    async def balance(self):
        try:
            token = self.jwt()
            headers = {'Authorization': 'Bearer ' + token}
            async with aiohttp.ClientSession(headers=headers) as session:
                r = await session.get('https://ccx.upbit.com/api/v1/funds', timeout=5)
                data = await r.json()

            if 'accounts' not in data.keys() and data['error']:
                debugger.info("API Key가 만료되었습니다. 다시 로그인합니다.")
                self.chrome(headless=True)
                token = self.sign_in(self.username, self.password)
                self.off()
                self.decrypt_token(token)
                return False, '', "API Key가 만료되었습니다. 다시 로그인합니다.", 5
            ret = {}
            for bal in data['accounts']:
                ret[bal['currency']] = float(bal['balance'])

            return True, ret, '', 0
        except Exception as e:
            return False, '', str(e), 3

    async def get_trading_fee(self):
        return True, 0.0025, '', 0

    async def get_transaction_fee(self):
        fees = {'BTC': 0.0005, 'ETH': 0.01, 'ETC': 0.01, 'BCH': 0.003, 'OMG': 0.4, 'POWR': 5.0, 'REP': 0.1,
                      'SNT': 15.0,
                      'STORJ': 4.0, 'MTL': 0.8, 'TIX': 3.0, 'LTC': 0.01, 'QTUM': 0.01, 'DGD': 0.04, 'XRP': 1.0,
                      'MYST': 3.0,
                      'BTG': 0.001, 'WAVES': 0.001, 'SNGLS': 3.5, 'XAUR': 2.5, 'MER': 0.1, 'EDG': 4.0, 'AMP': 10.0,
                      'MAID': 5.0, 'AGRS': 10.0, 'FUN': 60.0, 'ANT': 1.3, 'MANA': 45.0, 'SRN': 3.0, 'WAX': 5.0,
                      'ZRX': 3.5,
                      'VEE': 45.0, 'STEEM': 0.01, 'SBD': 0.01, 'BCPT': 6.0, 'BAT': 11.0, 'SALT': 1.0, 'BNT': 0.85,
                      'MCO': 0.5,
                      'RCN': 27.0, 'CFI': 40.0, 'HMQ': 17.0, 'WINGS': 6.0, 'NMR': 0.18, 'GUP': 13.0, 'SWT': 2.0,
                      'DNT': 50.0,
                      'GNT': 12.0, 'CVC': 11.0, 'PAY': 2.4, 'RLC': 3.5, 'ENG': 1.5, 'UKG': 13.0, 'VIB': 17.0,
                      'ADX': 3.0,
                      'QRL': 3.7, 'GNO': 0.03, 'PTOY': 22.0, 'ADT': 60.0, 'STRAT': 0.2, 'ADA': 0.5, 'TRX': 80.0,
                      '1ST': 9.0,
                      'LRC': 10.0, 'NEO': 0.0, 'XMR': 0.04, 'PIVX': 0.03, 'UP': 40.0, 'STORM': 250.0, 'ICX': 1.5,
                      'EOS': 0.8,
                      'DMT': 4.0, 'DASH': 0.002, 'ARK': 0.1, 'ZEC': 0.001, 'ARDR': 2.0, 'IGNIS': 2.0, 'XEM': 4.0,
                      'KMD': 0.002, 'GRS': 0.2, 'EMC2': 0.2, 'VTC': 0.02, 'LSK': 0.1, 'LUN': 0.5, 'POLY': 12.0,
                      'XLM': 0.01,
                      'XVG': 0.2, 'RDD': 2.0, 'EMC': 0.02, 'PRO': 2.0, 'SC': 0.1, 'GTO': 15.0, 'ONT': 0.1, 'ZIL': 30.0,
                      'BLT': 5.0, 'DCR': 0.05, 'AID': 35.0, 'NGC': 10.0, 'OCN': 500.0}
        for fee in fees.keys():
            fees[fee] = Decimal(fees[fee]).quantize(Decimal(10) ** -8)

        return True, fees, '', 0

    def currencies(self):
        return []

    def get_available_coin(self):
        coins = self.currencies()

        return [('BTC_' + coin) for coin in coins]

    async def get_deposit_addrs(self):
        token = self.jwt()
        ret = {}
        try:
            currencies = self.currencies()
            headers = {'Authorization': 'Bearer ' + token}
            async with aiohttp.ClientSession(headers=headers) as session:
                for coin in currencies:
                    param = {'currency': coin}
                    while True:
                        r = await session.get('https://ccx.upbit.com/api/v1/deposits/coin_address', params=param)
                        data = await r.json()
                        if 'error' in data and data['error']['name'] == 'V1::Exceptions::TooManyRequestCoinAddress':
                            continue
                        if 'deposit_address' in data.keys():
                            if '?dt=' in data['deposit_address']:
                                dt = data['deposit_address'].split('?dt=')
                                ret[coin] = dt[0]
                                ret[coin + 'TAG'] = dt[1]
                            else:
                                ret[coin] = data['deposit_address']

                        break
            return True, ret, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def get_precision(self, pair):
        return True, (-8, -8), '' , 0


class UpbitBTC(Upbit):
    def __init__(self, username, password, token, chat_id):
        super().__init__(username, password, token, chat_id)

        thr = Thread(target=self.connect_socket)
        thr.start()

    def connect_socket(self):
        self.ws = websocket.create_connection("wss://crix-websocket.upbit.com/sockjs/536/drct5y1t/websocket",
                                              sslopt={"cert_reqs": ssl.CERT_NONE})

        debugger.info("웹소켓 로딩중..")
        while True:
            try:
                received = self.ws.recv()
                if received == 'o' and not self.order_book:
                    debugger.info("UPBIT 웹소켓 접속완료!!")
                    payload = json.dumps(
                        [
                            "[{\"ticket\":\"ram macbook\"},{\"type\":\"recentCrix\",\"codes\":[\"CRIX.COINMARKETCAP.KRW-USDT\"]},{\"type\":\"crixTrade\",\"codes\":[\"CRIX.UPBIT.BTC-ETC\"]},{\"type\":\"crixOrderbook\",\"codes\":[\"CRIX.UPBIT.BTC-DASH\",\"CRIX.UPBIT.BTC-ETH\",\"CRIX.UPBIT.BTC-NEO\",\"CRIX.UPBIT.BTC-MTL\",\"CRIX.UPBIT.BTC-LTC\",\"CRIX.UPBIT.BTC-STRAT\",\"CRIX.UPBIT.BTC-XRP\",\"CRIX.UPBIT.BTC-ETC\",\"CRIX.UPBIT.BTC-OMG\",\"CRIX.UPBIT.BTC-SNT\",\"CRIX.UPBIT.BTC-WAVES\",\"CRIX.UPBIT.BTC-PIVX\",\"CRIX.UPBIT.BTC-XEM\",\"CRIX.UPBIT.BTC-ZEC\",\"CRIX.UPBIT.BTC-XMR\",\"CRIX.UPBIT.BTC-QTUM\",\"CRIX.UPBIT.BTC-GNT\",\"CRIX.UPBIT.BTC-LSK\",\"CRIX.UPBIT.BTC-STEEM\",\"CRIX.UPBIT.BTC-XLM\",\"CRIX.UPBIT.BTC-ARDR\",\"CRIX.UPBIT.BTC-KMD\",\"CRIX.UPBIT.BTC-ARK\",\"CRIX.UPBIT.BTC-STORJ\",\"CRIX.UPBIT.BTC-GRS\",\"CRIX.UPBIT.BTC-VTC\",\"CRIX.UPBIT.BTC-REP\",\"CRIX.UPBIT.BTC-EMC2\",\"CRIX.UPBIT.BTC-ADA\",\"CRIX.UPBIT.BTC-SBD\",\"CRIX.UPBIT.BTC-TIX\",\"CRIX.UPBIT.BTC-POWR\",\"CRIX.UPBIT.BTC-MER\",\"CRIX.UPBIT.BTC-BTG\",\"CRIX.UPBIT.BTC-ICX\",\"CRIX.UPBIT.BTC-EOS\",\"CRIX.UPBIT.BTC-STORM\",\"CRIX.UPBIT.BTC-TRX\",\"CRIX.UPBIT.BTC-MCO\",\"CRIX.UPBIT.BTC-SC\",\"CRIX.UPBIT.BTC-GTO\",\"CRIX.UPBIT.BTC-IGNIS\",\"CRIX.UPBIT.BTC-ONT\",\"CRIX.UPBIT.BTC-DCR\",\"CRIX.UPBIT.BTC-ZIL\",\"CRIX.UPBIT.BTC-POLY\",\"CRIX.UPBIT.BTC-ZRX\",\"CRIX.UPBIT.BTC-SRN\",\"CRIX.UPBIT.BTC-LOOM\", \"CRIX.UPBIT.BTC-BCH\"]}]"
                        ]
                    )
                    self.ws.send(payload)
                    debugger.info("UPBIT 데이터 요청중...")
                elif received[0] == 'a':
                    r = received.replace('\\', '')
                    data = json.loads(r[3:-2])

                    code = data['code']
                    currency = code.split('-')[-1]

                    if not self.order_book:
                        self.order_book = {
                            currency: data
                        }
                    else:
                        self.order_book[currency] = data
            except:
                self.order_book = None
                debugger.exception("소켓 끊어짐")
                while True:
                    try:
                        self.ws.close()
                        time.sleep(3)
                        self.ws = websocket.create_connection(
                            "wss://crix-websocket.upbit.com/sockjs/536/drct5y1t/websocket",
                            sslopt={"cert_reqs": ssl.CERT_NONE})

                        debugger.info("웹소켓 로딩중..")
                        break
                    except:
                        debugger.exception("소켓 끊어짐")

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        alt = Decimal(alt_amount)
        success, result, error, ts = self.buy_coin(currency_pair.split('_')[1], alt_amount)
        try:
            err = json.loads(result)['error']['message']
            if err:
                #   에러텍스트가 존재하는 경우
                debugger.info(err)
                return False, '', error, ts
        except:
            #   에러가 없는경우.
            pass

        if not success:
            debugger.info(error)
            return False, '', error, ts

        alt *= 1 - Decimal(td_fee)
        alt -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt = alt.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return True, alt, '', 0

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        while True:
            success, result, error, ts = self.sell_coin(currency_pair.split('_')[1], alt_amount)
            try:
                err = json.loads(result)['error']['message']
                if '부족합니다.' in err:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
                if err:
                    #   에러텍스트가 존재하는 경우
                    debugger.info(err)
                    time.sleep(ts)
                    continue
            except:
                #   에러가 없는경우.
                pass
            if success:
                break

            debugger.info(error)
            time.sleep(ts)

    def buy_coin(self, coin, amount):
        try:
            price = self.order_book[coin]['orderbookUnits'][0]['bidPrice']
        except Exception as e:
            return False, '', str(e), 5
        token = self.jwt()
        try:
            url = "https://ccx.upbit.com/api/v1/orders"
            headers = {
                'Authorization': 'Bearer ' + token
            }
            data = {
                'market': 'BTC-' + coin,
                'ord_type': 'limit',
                'side': 'bid',
                'price': price * 1.05,
                'volume': '{}'.format(amount)
            }
            r = requests.post(url, headers=headers, json=data)

            return True, r.text, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def sell_coin(self, coin, amount):
        try:
            price = self.order_book[coin]['orderbookUnits'][0]['askPrice']
        except Exception as e:
            return False, '', str(e), 5
        token = self.jwt()
        try:
            url = "https://ccx.upbit.com/api/v1/orders"
            headers = {
                'Authorization': 'Bearer ' + token
            }
            data = {
                'market': 'BTC-' + coin,
                'ord_type': 'limit',
                'side': 'ask',
                'price': price * 0.95,
                'volume': '{}'.format(amount)
            }
            r = requests.post(url, headers=headers, json=data)

            return True, r.text, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def currencies(self):
        return ["KRW", "BTC", "ETH", "ETC", "BCH", "OMG", "POWR", "REP", "SNT", "STORJ", "MTL", "TIX", "LTC", "QTUM",
                "DGD",
                "XRP", "MYST", "BTG", "WAVES", "SNGLS", "XAUR", "MER", "EDG", "AMP", "MAID", "AGRS", "FUN", "ANT",
                "MANA", "SRN", "WAX", "ZRX", "VEE", "STEEM", "SBD", "BCPT", "BAT", "SALT", "BNT", "MCO", "RCN", "CFI",
                "HMQ", "WINGS", "NMR", "GUP", "SWT", "DNT", "GNT", "CVC", "PAY", "RLC", "ENG", "UKG", "VIB", "ADX",
                "QRL", "GNO", "PTOY", "ADT", "STRAT", "ADA", "TRX", "1ST", "LRC", "NEO", "XMR", "PIVX", "UP", "STORM",
                "ICX", "EOS", "DMT", "DASH", "ARK", "ZEC", "ARDR", "IGNIS", "XEM", "KMD", "GRS", "EMC2", "VTC", "LSK",
                "LUN", "POLY", "XLM", "XVG", "RDD", "EMC", "PRO", "SC", "GTO", "ONT", "ZIL", "BLT", "DCR", "AID", "NGC",
                "OCN"]

    async def get_curr_avg_orderbook(self, currencies, default_btc=1):
        ret = {}
        #   만약 err과 st가 설정아 안된 경우
        if not self.order_book:
            return False, '', "오더북 불러오기 에러", 5
        data = self.order_book

        for c in data:
            if 'BTC_' + c.upper() not in currencies:
                #   parameter 로 들어온 페어가 아닌 경우에는 제외
                continue
            ret['BTC_' + c.upper()] = {}
            for order_type in ['bids', 'asks']:
                try:
                    rows = data[c]['orderbookUnits']
                except KeyError as e:
                    return False, '', "오더북 불러오기 에러", 5
                total_price = Decimal(0.0)
                total_amount = Decimal(0.0)
                for row in rows:
                    if order_type == 'bids':
                        total_price += Decimal(row['bidPrice']) * Decimal(row['bidSize'])
                        total_amount += Decimal(row['bidSize'])
                    else:
                        total_price += Decimal(row['askPrice']) * Decimal(row['askSize'])
                        total_amount += Decimal(row['askSize'])

                    if total_price >= default_btc:
                        break

                ret['BTC_' + c.upper()][order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)
        return True, ret, '', 0

    async def compare_orderbook(self, other, coins=[], default_btc=1):
        # currency_pairs = ['BTC_' + coin for coin in coins if coin != 'BTC']
        currency_pairs = coins
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            upbit_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs, default_btc),
                                                              other.get_curr_avg_orderbook(currency_pairs, default_btc))
            success, upbit_avg_orderbook, err, st = upbit_result
            success2, other_avg_orderbook, err2, st2 = other_result
            if success and success2:
                m_to_s = {}
                for currency_pair in currency_pairs:
                    m_ask = upbit_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in currency_pairs:
                    m_bid = upbit_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                ret = (upbit_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m})

                return True, ret, '', 0
            else:
                future = asyncio.sleep(st) if st > st2 else asyncio.sleep(st2)
                await future
                continue
        else:
            if not err:
                return False, '', err2, st2
            else:
                return False, '', err, st

    def fee_count(self):
        return 1


class UpbitUSDT(Upbit):
    def __init__(self, username, password, token, chat_id):
        super().__init__(username, password, token, chat_id)

        thr = Thread(target=self.connect_socket)
        thr.start()

    def connect_socket(self):
        self.ws = websocket.create_connection("wss://crix-websocket.upbit.com/sockjs/536/drct5y1t/websocket",
                                              sslopt={"cert_reqs": ssl.CERT_NONE})

        debugger.info("웹소켓 로딩중..")
        while True:
            try:
                received = self.ws.recv()
                if received == 'o' and not self.order_book:
                    debugger.info("UPBIT 웹소켓 접속완료!!")
                    payload = json.dumps(
                        [
                            "[{\"ticket\":\"ram macbook\"},{\"type\":\"recentCrix\",\"codes\":[\"CRIX.COINMARKETCAP.KRW-USDT\"]},{\"type\":\"crixTrade\",\"codes\":[\"CRIX.UPBIT.USDT-ETC\"]},{\"type\":\"crixOrderbook\",\"codes\":[\"CRIX.UPBIT.USDT-BTC\",\"CRIX.UPBIT.USDT-DASH\",\"CRIX.UPBIT.USDT-ETH\",\"CRIX.UPBIT.USDT-NEO\",\"CRIX.UPBIT.USDT-BCH\",\"CRIX.UPBIT.USDT-MTL\",\"CRIX.UPBIT.USDT-LTC\",\"CRIX.UPBIT.USDT-STRAT\",\"CRIX.UPBIT.USDT-XRP\",\"CRIX.UPBIT.USDT-ETC\",\"CRIX.UPBIT.USDT-OMG\",\"CRIX.UPBIT.USDT-SNT\",\"CRIX.UPBIT.USDT-WAVES\",\"CRIX.UPBIT.USDT-PIVX\",\"CRIX.UPBIT.USDT-XEM\",\"CRIX.UPBIT.USDT-ZEC\",\"CRIX.UPBIT.USDT-XMR\",\"CRIX.UPBIT.USDT-QTUM\",\"CRIX.UPBIT.USDT-GNT\",\"CRIX.UPBIT.USDT-LSK\",\"CRIX.UPBIT.USDT-STEEM\",\"CRIX.UPBIT.USDT-XLM\",\"CRIX.UPBIT.USDT-ARDR\",\"CRIX.UPBIT.USDT-KMD\",\"CRIX.UPBIT.USDT-ARK\",\"CRIX.UPBIT.USDT-STORJ\",\"CRIX.UPBIT.USDT-GRS\",\"CRIX.UPBIT.USDT-VTC\",\"CRIX.UPBIT.USDT-REP\",\"CRIX.UPBIT.USDT-EMC2\",\"CRIX.UPBIT.USDT-ADA\",\"CRIX.UPBIT.USDT-SBD\",\"CRIX.UPBIT.USDT-TIX\",\"CRIX.UPBIT.USDT-POWR\",\"CRIX.UPBIT.USDT-MER\",\"CRIX.UPBIT.USDT-BTG\",\"CRIX.UPBIT.USDT-ICX\",\"CRIX.UPBIT.USDT-EOS\",\"CRIX.UPBIT.USDT-STORM\",\"CRIX.UPBIT.USDT-TRX\",\"CRIX.UPBIT.USDT-MCO\",\"CRIX.UPBIT.USDT-SC\",\"CRIX.UPBIT.USDT-GTO\",\"CRIX.UPBIT.USDT-IGNIS\",\"CRIX.UPBIT.USDT-ONT\",\"CRIX.UPBIT.USDT-DCR\",\"CRIX.UPBIT.USDT-ZIL\",\"CRIX.UPBIT.USDT-POLY\",\"CRIX.UPBIT.USDT-ZRX\",\"CRIX.UPBIT.USDT-SRN\",\"CRIX.UPBIT.USDT-LOOM\"]}]"
                        ]

                    )
                    self.ws.send(payload)
                    debugger.info("UPBIT 데이터 요청중...")
                elif received[0] == 'a':
                    r = received.replace('\\', '')
                    data = json.loads(r[3:-2])

                    code = data['code']
                    currency = code.split('-')[-1]

                    if not self.order_book:
                        self.order_book = {
                            currency: data
                        }
                    else:
                        self.order_book[currency] = data
            except:
                self.order_book = None
                debugger.exception("소켓 끊어짐")
                while True:
                    try:
                        self.ws.close()
                        time.sleep(3)
                        self.ws = websocket.create_connection(
                            "wss://crix-websocket.upbit.com/sockjs/536/drct5y1t/websocket",
                            sslopt={"cert_reqs": ssl.CERT_NONE})

                        debugger.info("웹소켓 로딩중..")
                        break
                    except:
                        debugger.exception("소켓 끊어짐")

    def base_to_alt(self, currency_pair, btc_amount, alt_amount, td_fee, tx_fee):
        alt = Decimal(alt_amount)
        success, result, error, ts = self.sell_coin('BTC', btc_amount)
        try:
            err = json.loads(result)['error']['message']
            if err:
                #   에러텍스트가 존재하는 경우
                debugger.info(err)
                time.sleep(ts)
                return False
        except:
            #   에러가 없는경우.
            pass

        if not success:
            debugger.info(error)
            time.sleep(ts)
            return False

        while True:
            success, result, error, ts = self.buy_coin(currency_pair.split('_')[1], alt_amount)
            try:
                err = json.loads(result)['error']['message']
                if err:
                    #   에러텍스트가 존재하는 경우
                    debugger.info(err)
                    time.sleep(ts)
                    continue
            except:
                #   에러가 없는경우.
                pass
            if success:
                break
            debugger.info(error)
            time.sleep(ts)

        alt *= ((1 - Decimal(td_fee)) ** 2)
        alt -= Decimal(tx_fee[currency_pair.split('_')[1]])
        alt = alt.quantize(Decimal(10) ** -4, rounding=ROUND_DOWN)

        return alt

    def alt_to_base(self, currency_pair, btc_amount, alt_amount):
        while True:
            success, result, error, ts = self.sell_coin(currency_pair.split('_')[1], alt_amount)
            try:
                err = json.loads(result)['error']['message']
                if '부족합니다' in err:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
                if err:
                    #   에러텍스트가 존재하는 경우
                    debugger.info(err)
                    time.sleep(ts)
                    continue
            except:
                #   에러가 없는경우.
                pass
            if success:
                break
            debugger.info(error)
            time.sleep(ts)
        while True:
            success, result, error, ts = self.buy_coin('BTC', btc_amount)
            try:
                err = json.loads(result)['error']['message']
                if '부족합니다' in err:
                    alt_amount -= Decimal(0.0001).quantize(Decimal(10) ** -4)
                    continue
                if err:
                    #   에러텍스트가 존재하는 경우
                    debugger.info(err)
                    time.sleep(ts)
                    continue
            except:
                #   에러가 없는경우.
                pass
            if success:
                break
            debugger.info(error)
            time.sleep(ts)

    def buy_coin(self, coin, amount):
        try:
            price = self.order_book[coin]['orderbookUnits'][0]['bidPrice']
        except Exception as e:
            return False, '', str(e), 5
        token = self.jwt()
        try:
            url = "https://ccx.upbit.com/api/v1/orders"
            headers = {
                'Authorization': 'Bearer ' + token
            }
            data = {
                'market': 'USDT-' + coin,
                'ord_type': 'limit',
                'side': 'bid',
                'price': price * 1.05,
                'volume': '{}'.format(amount)
            }
            debugger.debug(data)
            r = requests.post(url, headers=headers, json=data)

            return True, r.text, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def sell_coin(self, coin, amount):
        try:
            price = self.order_book[coin]['orderbookUnits'][0]['askPrice']
        except Exception as e:
            return False, '', str(e), 5
        token = self.jwt()
        try:
            url = "https://ccx.upbit.com/api/v1/orders"
            headers = {
                'Authorization': 'Bearer ' + token
            }
            data = {
                'market': 'USDT-' + coin,
                'ord_type': 'limit',
                'side': 'ask',
                'price': price * 0.95,
                'volume': '{}'.format(amount)
            }
            debugger.debug(data)
            r = requests.post(url, headers=headers, json=data)

            return True, r.text, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def currencies(self):
        return ['ETC', 'DASH', 'ETH', 'NEO', 'BCH', 'LTC', 'XRP', 'OMG', 'ZEC', 'XMR', 'ADA', 'BTG', 'TRX', 'SC', 'DCR']

    async def get_curr_avg_orderbook(self, currencies, default_btc=1):
        ret = {}
        err = "오더북 조회 에러"
        st = 5
        #   만약 err과 st가 설정아 안된 경우
        data = self.order_book.copy()
        if not data:
            return False, '', err, st

        btc_avg = {}
        for order_type in ['bids', 'asks']:
            try:
                rows = data['BTC']['orderbookUnits']
            except KeyError as e:
                return False, '', err, st
            total_price = Decimal(0.0)
            total_amount = Decimal(0.0)
            for row in rows:
                if order_type == 'bids':
                    total_price += Decimal(row['bidPrice']) * Decimal(row['bidSize'])
                    total_amount += Decimal(row['bidSize'])
                else:
                    total_price += Decimal(row['askPrice']) * Decimal(row['askSize'])
                    total_amount += Decimal(row['askSize'])

                if total_amount >= default_btc:
                    break

            btc_avg[order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)

        debugger.debug('BTC: {}'.format(btc_avg))

        del data['BTC']

        try:
            for c in data:
                if 'BTC_' + c.upper() not in currencies:
                    #   parameter 로 들어온 페어가 아닌 경우에는 제외
                    continue
                ret['BTC_' + c.upper()] = {}
                for order_type in ['bids', 'asks']:
                    try:
                        rows = data[c]['orderbookUnits']
                    except KeyError as e:
                        return False, '', err, st
                    total_price = Decimal(0.0)
                    total_amount = Decimal(0.0)
                    for row in rows:
                        if order_type == 'bids':
                            total_price += Decimal(row['bidPrice']) / btc_avg['asks'] * Decimal(row['bidSize'])
                            total_amount += Decimal(row['bidSize'])
                        else:
                            total_price += Decimal(row['askPrice']) / btc_avg['bids'] * Decimal(row['askSize'])
                            total_amount += Decimal(row['askSize'])

                        if total_price >= default_btc:
                            break

                    ret['BTC_' + c.upper()][order_type] = (total_price / total_amount).quantize(Decimal(10) ** -8)

                debugger.debug('{}: {}'.format(c.upper(), ret['BTC_' + c.upper()]))
        except RuntimeError:
            return False, '', err, st
        return True, ret, '', 0

    async def compare_orderbook(self, other, coins=[], default_btc=1):
        # currency_pairs = ['BTC_' + coin for coin in coins if coin != 'BTC']
        currency_pairs = coins
        err = ""
        st = 5
        err2 = ""
        st2 = 5
        for _ in range(3):
            upbit_result, other_result = await asyncio.gather(self.get_curr_avg_orderbook(currency_pairs, default_btc),
                                                              other.get_curr_avg_orderbook(currency_pairs, default_btc))
            success, upbit_avg_orderbook, err, st = upbit_result
            success2, other_avg_orderbook, err2, st2 = other_result
            if success and success2:
                m_to_s = {}
                for currency_pair in currency_pairs:
                    m_ask = upbit_avg_orderbook[currency_pair]['asks']
                    s_bid = other_avg_orderbook[currency_pair]['bids']
                    m_to_s[currency_pair] = float(((s_bid - m_ask) / m_ask).quantize(Decimal(10) ** -8))

                s_to_m = {}
                for currency_pair in currency_pairs:
                    m_bid = upbit_avg_orderbook[currency_pair]['bids']
                    s_ask = other_avg_orderbook[currency_pair]['asks']
                    s_to_m[currency_pair] = float(((m_bid - s_ask) / s_ask).quantize(Decimal(10) ** -8))

                ret = (upbit_avg_orderbook, other_avg_orderbook, {'m_to_s': m_to_s, 's_to_m': s_to_m})

                return True, ret, '', 0
            else:
                future = asyncio.sleep(st) if st > st2 else asyncio.sleep(st2)
                await future
                continue
        else:
            if not err:
                return False, '', err2, st2
            else:
                return False, '', err, st

    def fee_count(self):
        return 2


class UpbitKRW(UpbitUSDT):
    def __init__(self, username, password, token, chat_id):
        super().__init__(username, password, token, chat_id)

    def connect_socket(self):
        self.ws = websocket.create_connection("wss://crix-websocket.upbit.com/sockjs/536/drct5y1t/websocket",
                                              sslopt={"cert_reqs": ssl.CERT_NONE})

        debugger.info("웹소켓 로딩중..")
        while True:
            try:
                received = self.ws.recv()
                if received == 'o' and not self.order_book:
                    debugger.info("UPBIT 웹소켓 접속완료!!")
                    payload = json.dumps(
                        [
                            "[{\"ticket\":\"ram macbook\"},{\"type\":\"crixOrderbook\",\"codes\":[\"CRIX.UPBIT.KRW-BTC\",\"CRIX.UPBIT.KRW-DASH\",\"CRIX.UPBIT.KRW-ETH\",\"CRIX.UPBIT.KRW-NEO\",\"CRIX.UPBIT.KRW-BCC\",\"CRIX.UPBIT.KRW-MTL\",\"CRIX.UPBIT.KRW-LTC\",\"CRIX.UPBIT.KRW-STRAT\",\"CRIX.UPBIT.KRW-XRP\",\"CRIX.UPBIT.KRW-ETC\",\"CRIX.UPBIT.KRW-OMG\",\"CRIX.UPBIT.KRW-SNT\",\"CRIX.UPBIT.KRW-WAVES\",\"CRIX.UPBIT.KRW-PIVX\",\"CRIX.UPBIT.KRW-XEM\",\"CRIX.UPBIT.KRW-ZEC\",\"CRIX.UPBIT.KRW-XMR\",\"CRIX.UPBIT.KRW-QTUM\",\"CRIX.UPBIT.KRW-GNT\",\"CRIX.UPBIT.KRW-LSK\",\"CRIX.UPBIT.KRW-STEEM\",\"CRIX.UPBIT.KRW-XLM\",\"CRIX.UPBIT.KRW-ARDR\",\"CRIX.UPBIT.KRW-KMD\",\"CRIX.UPBIT.KRW-ARK\",\"CRIX.UPBIT.KRW-STORJ\",\"CRIX.UPBIT.KRW-GRS\",\"CRIX.UPBIT.KRW-VTC\",\"CRIX.UPBIT.KRW-REP\",\"CRIX.UPBIT.KRW-EMC2\",\"CRIX.UPBIT.KRW-ADA\",\"CRIX.UPBIT.KRW-SBD\",\"CRIX.UPBIT.KRW-TIX\",\"CRIX.UPBIT.KRW-POWR\",\"CRIX.UPBIT.KRW-MER\",\"CRIX.UPBIT.KRW-BTG\",\"CRIX.UPBIT.KRW-ICX\",\"CRIX.UPBIT.KRW-EOS\",\"CRIX.UPBIT.KRW-STORM\",\"CRIX.UPBIT.KRW-TRX\",\"CRIX.UPBIT.KRW-MCO\",\"CRIX.UPBIT.KRW-SC\",\"CRIX.UPBIT.KRW-GTO\",\"CRIX.UPBIT.KRW-IGNIS\",\"CRIX.UPBIT.KRW-ONT\",\"CRIX.UPBIT.KRW-DCR\",\"CRIX.UPBIT.KRW-ZIL\",\"CRIX.UPBIT.KRW-POLY\",\"CRIX.UPBIT.KRW-ZRX\",\"CRIX.UPBIT.KRW-SRN\",\"CRIX.UPBIT.KRW-LOOM\"]}]"
                        ]
                    )
                    self.ws.send(payload)
                    debugger.info("UPBIT 데이터 요청중...")
                elif received[0] == 'a':
                    r = received.replace('\\', '')
                    data = json.loads(r[3:-2])

                    code = data['code']
                    currency = code.split('-')[-1]

                    if not self.order_book:
                        self.order_book = {
                            currency: data
                        }
                    else:
                        self.order_book[currency] = data
            except:
                self.order_book = None
                debugger.exception("소켓 끊어짐")
                while True:
                    try:
                        self.ws.close()
                        time.sleep(3)
                        self.ws = websocket.create_connection(
                            "wss://crix-websocket.upbit.com/sockjs/536/drct5y1t/websocket",
                            sslopt={"cert_reqs": ssl.CERT_NONE})

                        debugger.info("웹소켓 로딩중..")
                        break
                    except:
                        debugger.exception("소켓 끊어짐")

    def get_step(self, price):
        if price >= 2000000:
            return 1000
        elif 2000000 > price >= 1000000:
            return 500
        elif 1000000 > price >= 500000:
            return 100
        elif 500000 > price >= 100000:
            return 50
        elif 100000 > price >= 10000:
            return 10
        elif 10000 > price >= 1000:
            return 5
        elif price < 10:
            return 0.01
        elif price < 100:
            return 0.1
        elif price < 1000:
            return 1

    def buy_coin(self, coin, amount):
        try:
            price = self.order_book[coin]['orderbookUnits'][0]['bidPrice']
        except Exception as e:
            return False, '', str(e), 5
        token = self.jwt()
        try:
            url = "https://ccx.upbit.com/api/v1/orders"
            headers = {
                'Authorization': 'Bearer ' + token
            }
            data = {
                'market': 'KRW-' + coin,
                'ord_type': 'limit',
                'side': 'bid',
                'price': (price * 1.05) + (self.get_step(price*1.05) - ((price * 1.05) % self.get_step(price*1.05))),
                'volume': '{}'.format(amount)
            }
            r = requests.post(url, headers=headers, json=data)

            return True, r.text, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def sell_coin(self, coin, amount):
        try:
            price = self.order_book[coin]['orderbookUnits'][0]['askPrice']
        except Exception as e:
            return False, '', str(e), 5
        token = self.jwt()
        try:
            url = "https://ccx.upbit.com/api/v1/orders"
            headers = {
                'Authorization': 'Bearer ' + token
            }
            data = {
                'market': 'KRW-' + coin,
                'ord_type': 'limit',
                'side': 'ask',
                'price': (price * 0.95) - ((price * 0.95) % self.get_step(price*0.95)),
                'volume': '{}'.format(amount)
            }
            r = requests.post(url, headers=headers, json=data)

            return True, r.text, '', 0
        except Exception as e:
            return False, '', str(e), 5

    def currencies(self):
        return ['DASH', 'ETH', 'ENO', 'BCC', 'MTL', 'LTC', 'STRAT', 'XRP', 'ETC', 'OMG', 'SNT', 'WAVES', 'PIVX', 'XEM',
                'ZEC', 'XMR', 'QTUM', 'GNT', 'LSK', 'STEEM', 'XLM', 'ARDR', 'KMD', 'ARK', 'STORJ', 'GRS', 'VTC', 'REP',
                'EMC2', 'ADA', 'SBC', 'TIX', 'POWR', 'MER', 'BTG', 'ICX', 'EOS', 'STORM', 'TRX', 'MCO', 'SC', 'GTO',
                'IGNIS', 'ONT', 'DCR', 'ZIL', 'POLY', 'ZRX', 'SRN', 'LOOM']

    async def get_trading_fee(self):
        return True, 0.0005, '', 0
