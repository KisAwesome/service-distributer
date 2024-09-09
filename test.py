import zono.socket.client
import zono.socket.server as server
import zono.socket.server.modules
import time
import sys


import zono.song


class Server(server.Server):
    def __init__(self):
        self.interval = 0
        self.max_connections = 10
    modules = [zono.socket.server.modules.Logging(True)]
    @server.event('startup')
    def s(self,ctx):
        c = zono.socket.client.Client()
        c.connect(('localhost',8080))
        print(c.request('register_service',_recv=True,pkt=dict(service='test',test_path=dict(path='uptime',protocol='socket'),port=ctx.app.port)))
        c.close()

    
    @server.route('uptime')
    def uptime(self,ctx):
        time.sleep(self.interval)
        ctx.send(dict(connected=len(ctx.app.sessions),max_connections=self.max_connections,running=100))


    @server.route('interval')
    def interval(self,ctx):
        if ctx.pkt.get('time',None) is None:
            return ctx.send('No')
        self.interval = int(ctx.pkt.get('time'))
        ctx.send('Interval set')
port = 4505
if len(sys.argv)>1:
    port = int(sys.argv[1])

s = Server(port=port)


s.run()