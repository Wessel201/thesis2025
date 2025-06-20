import asyncio
import aiohttp
import aiohttp.web
import time
from multiprocessing import Process


DELAY = 0.05

async def handle(request):
    """Server handler: waits 50ms, returns 1KB of data."""
    await asyncio.sleep(DELAY)
    return aiohttp.web.Response(body=b'x' * 1024) # 1KB body

async def init_app():
    """Initializes the aiohttp server application."""
    app = aiohttp.web.Application()
    app.router.add_get('/', handle)
    return app

def run_server(port):
    """Entry point for the server process."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = loop.run_until_complete(init_app())
    runner = aiohttp.web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = aiohttp.web.TCPSite(runner, '127.0.0.1', port)
    loop.run_until_complete(site.start())
    loop.run_forever()


class Server():
    def setup(self):
        """Starts the background HTTP server."""
        port = 8080
        self.url = f"http://127.0.0.1:{port}"
        port = int(self.url.split(':')[-1])
        self.server_process = Process(target=run_server, args=(port,))
        self.server_process.start()
        time.sleep(2)
        print(f"Server started on port {port} with PID {self.server_process.pid}")


port = 8080
A = Server()
A.setup()
