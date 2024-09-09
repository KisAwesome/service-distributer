import zono.asynchronous.server as server
import zono.asynchronous.server.modules as modules
import zono.asynchronous.intervals as intervals
import zono.socket.client
import zono.colorlogger
import asyncio
import time


class Server(server.Server):
    modules = [modules.Logging(True)]

    def __init__(self, services=[], kvstore={}):
        self.services = {i: [] for i in services}
        self.kvstore = kvstore
        self.logger = zono.colorlogger.create_logger("service_dist", level=10)
        self.service_info = {}
        self.service_lock = asyncio.Lock()
        self.kvlock = asyncio.Lock()

    @server.event("on_start")
    async def start(self, ctx):
        self.interval = await intervals.set_interval(5, self.echo)
    async def remove_service_handler(self,addr,service):
        async with self.service_lock:
            self.service_info.pop(addr, None)
            self.services[service].remove(addr)


    async def check_uptime(self,addr,service):
        c = zono.socket.client.Client()
        t = time.perf_counter()
        try:
            async with asyncio.timeout(5):
                await asyncio.to_thread(c.connect, addr)
        except asyncio.TimeoutError:
            self.logger.info(
                f"{addr} for {service} timed out on connection and is now removed from options"
            )
            return await self.remove_service_handler(addr, service)

        except zono.socket.client.ConnectionFailed:
            self.logger.info(
                f"{addr} for {service} refused to connect and now removed from options"
            )
            return await self.remove_service_handler(addr, service)

        try:
            async with asyncio.timeout(5):
                await asyncio.to_thread(c.send, dict(path=self.service_info[addr]["path"]))
                if not await asyncio.to_thread(c.recv):
                    raise asyncio.TimeoutError()
        except asyncio.TimeoutError:
            self.logger.info(
                f"{addr} for {service} timed out on connection and is now removed from options"
            )
            return await self.remove_service_handler(addr, service)

        ep = time.perf_counter()-t
        self.service_info[addr]['ping'] = ep
        self.logger.info(f"Pinged {addr} for {service} responded in {ep} seconds")
        await asyncio.to_thread(c.close)

    async def echo(self):
        async with self.service_lock:
            service_copy = self.services.copy().items()
        async with asyncio.TaskGroup() as tg:
            for service, ips in service_copy:
                for addr in ips[:]:
                    tg.create_task(self.check_uptime(addr, service))
               
    @server.route(
        "register_service",
        server.needs_attr(
            "service",
            "test_path",
            "port",
            fail=dict(success=False, info="Incomplete packet"),
        ),
    )
    async def register_service(self, ctx):
        if ctx.pkt.get("service") not in self.services:
            return await ctx.send(dict(success=False, info="Service does not exist"))

        addr = (ctx.addr[0], ctx.pkt.get("port"))
        if addr in self.services[ctx.pkt.get("service")]:
            return await ctx.send(
                dict(
                    success=False,
                    info="Service is already registered with same address",
                )
            )
        async with self.service_lock:
            self.services[ctx.pkt.get("service")].append((addr))
            self.service_info[addr] = dict(ping=None,service=ctx.pkt.get('service'),**ctx.pkt.get("test_path"),addr=addr)

        await ctx.send(dict(success=True, info="Service registered"))

    
    @server.route('get',server.needs_attr('service'))
    async def get(self,ctx):
        if ctx.pkt.get("service") not in self.services:
            return await ctx.send(dict(success=False, info="Service does not exist"))
        async with self.service_lock:
            services = sorted([self.service_info[i] for i in self.services[ctx.pkt.get("service")]],key=lambda x:x['ping'])
        if services:
            address = services[0]['addr']
        else:
            address = None

        await ctx.send(dict(success=True, address=address))



    @server.route('getkey',server.needs_attr('key'))
    async def getkey(self,ctx):
        async with self.kvlock:
            return await ctx.send(dict(success=True,value=self.kvstore.get(ctx.pkt.get('key'))))
        
    @server.route('setkey',server.needs_attr('key','value'))
    async def setkey(self,ctx):
        async with self.kvlock:
            self.kvstore[ctx.pkt.key] = ctx.pkt.value
        await ctx.send(dict(success=True))
        

        

s = Server(services=["test"])


s.start()