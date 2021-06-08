from Poloniex.poloniex import Poloniex
from Korbit.korbit import korbit_class
import asyncio

if __name__ == '__main__':
    p = Poloniex('V3SK7BOA-DN2YNUW7-H8GH5Y24-CA3UB86X', '70f27533f09b2f39006eb4f41326246ffcf213a326991c15c70d3020904b722072f1aa120a0343aa0226e03f8a84f548f3cc3a68da5ce3ea56f3f7f7592a778b')
    a = p.get_deposit_addrs()
    a = p.public_api('returnTicker')
    p.get_current_prices()
    # k = korbit_class('SR4Fq6JznJKlvZBJ1mlL4air3Ef8NrT3ekYaUSaRzzfSwMTtefn9vCoE9Xm9h', 'HmAzNkzS8GPxw21tn97MEYhgluYE2XUpWIqgxA4ZaRIr1ms9C2r3aBYElwaea', 'songsb13@gmail.com', 'S!tnsqja7721')
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(p.poloniex__korbit, '127.0.0.1', 8888, loop=loop)
    server = loop.run_until_complete(coro)

    # Serve requests until Ctrl+C is pressed
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    # Close the server
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
    # p.poloniex__korbit(k)
    # print(_t)