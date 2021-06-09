import asyncio
import json


async def asyncio_client(message, loop):
    reader, writer = await asyncio.open_connection('127.0.0.1', 8888,
                                                   loop=loop)

    print('Send: %r' % message)
    writer.write(message.encode())
    while True:
        try:
            data = await reader.read(4096)
            print('Received: %r' % data.decode())
        except KeyboardInterrupt:
            print("Close")
            break


if __name__ == '__main__':
    data = {'korbit': {'api_key': 'KORBIT API',
                       'secret': 'KORBIT SECRET',
                       'id': 'KORBIT EMAIL ACCOUNT',
                       'pass': 'KORBIT PASSWORD'},
            'poloniex': {'api_key': 'POLONIEX API',
                       'secret': 'POLONIEX SECRET'},
            'default_btc': 1}
    message = json.dumps(data)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio_client(message, loop))
    loop.close()