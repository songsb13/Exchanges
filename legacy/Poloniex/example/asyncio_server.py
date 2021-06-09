import asyncio
import json
from Poloniex.poloniex import Poloniex
from Korbit.korbit import korbit_class


async def asyncio_server(reader, writer):
    data = await reader.read(4096)
    d_data = data.decode()
    j_data = json.loads(d_data)
    addr = writer.get_extra_info('peername')
    print("Received %r from %r" % (j_data['poloniex']['api_key'], addr))

    korbit = korbit_class(j_data['korbit']['api_key'], j_data['korbit']['secret'], j_data['korbit']['id'],
                          j_data['korbit']['pass'])
    p = Poloniex(j_data['poloniex']['api_key'], j_data['poloniex']['secret'])
    default_btc = j_data['default_btc']

    while True:
        try:
            ret_j_data = await p.poloniex__korbit(korbit, default_btc)

            print("Send To %r:%r" % (addr[0], addr[1]))
            writer.write(json.dumps(ret_j_data).encode())
            await writer.drain()
        except ConnectionResetError:
            print("Close %r:%r" % (addr[0], addr[1]))
            break

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(asyncio_server, '127.0.0.1', 8888, loop=loop)
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