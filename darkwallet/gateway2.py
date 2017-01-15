import asyncio
import json
import signal
import sys
import websockets

import zmq.asyncio
loop = zmq.asyncio.ZMQEventLoop()
asyncio.set_event_loop(loop)

import libbitcoin.server

from darkwallet.wallet_interface import WalletInterface

class Gateway:

    def __init__(self, settings):
        self.settings = settings

        self.context = libbitcoin.server.Context()
        self._wallet = WalletInterface(self.context, settings)

    def stop(self):
        self.context.stop()
        self._wallet.stop()

    async def _accept(self, websocket, path):
        print("Connection opened.")
        try:
            while True:
                await self._process(websocket, path)
        except websockets.ConnectionClosed:
            print("Closing connection.")

    async def _process(self, websocket, path):
        message = await websocket.recv()
        try:
            request = json.loads(message)
        except json.JSONDecodeError:
            print("Error: decoding request", file=sys.stderr)
            return

        # Check request is correctly formed.
        if not self._check(request):
            print("Error: malformed request:", message, file=sys.stderr)
            return

        if request["command"] in self._wallet.commands:
            response = await self._wallet.handle(request)
        else:
            print("Error: unhandled command. Dropping:",
                  message, file=sys.stderr)
            return

        message = json.dumps(response)
        await websocket.send(message)

    def _check(self, request):
        # {
        #   "command": ...
        #   "id": ...
        #   "params": [...]
        # }
        return ("command" in request) and ("id" in request) and \
            ("params" in request and type(request["params"]) == list)

    async def serve(self):
        port = self.settings.port
        return await websockets.serve(self._accept, "localhost", port)

def start_ws(settings):
    gateway = Gateway(settings)

    tasks = [gateway.serve()]

    # Handle CTRL-C
    def signal_handler():
        print("Stopping darkwallet-daemon...")
        gateway.stop()
        loop.stop()

    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.run_until_complete(asyncio.wait(tasks))
    loop.run_forever()

