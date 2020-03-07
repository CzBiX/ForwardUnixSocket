#!/usr/bin/python3

"""
Cygwin/msysgit to Unix socket proxy
============================

This small script is intended to help use Cygwin/msysgit sockets with the Windows Linux Subsystem.

It was specifically designed to pass SSH keys from the KeeAgent module of KeePass secret management application to the
ssh utility running in the WSL (it only works with Linux sockets). However, my guess is that it will have uses for other
applications as well.

In order to efficiently use it, I add it at the end of the ~/.bashrc file, like this:
    export SSH_AUTH_SOCK="/tmp/.ssh-auth-sock"
    ~/bin/socket2unix-socket.py --daemon /mnt/c/Users/User/keeagent.sock:$SSH_AUTH_SOCK
"""


import argparse
import asyncio
import os
import re
import sys
import errno

def read_ip():
    with open('/etc/resolv.conf') as f:
        lines = f.readlines()
        line = lines[-1].rstrip()
        return line.split(' ')[-1]

localhost_ip = read_ip()

# NOTE: Taken from http://stackoverflow.com/a/6940314
def PidExists(pid):
    """Check whether pid exists in the current process table.
    UNIX only.
    """
    if pid < 0:
        return False
    if pid == 0:
        # According to "man 2 kill" PID 0 refers to every process
        # in the process group of the calling process.
        # On certain systems 0 is a valid PID but we have no way
        # to know that in a portable fashion.
        raise ValueError('invalid PID 0')
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:
            # ESRCH == No such process
            return False
        elif err.errno == errno.EPERM:
            # EPERM clearly means there's a process to deny access to
            return True
        else:
            # According to "man 2 kill" possible error values are
            # (EINVAL, EPERM, ESRCH)
            raise
    else:
        return True

class ForwardServer:
    """
    This is the "server" listening for connections on the Unix socket.
    """
    def __init__(self, is_cygwin, upstream_socket_path):
        self.is_cygwin = is_cygwin
        (self.port, self.guid) = self.load_socket_file(upstream_socket_path)

    def load_socket_file(self, path):
        with open(path, 'r') as f:
            line = f.readline()

        m = re.search(r'>(\d+)(?: s)? ([\w\d-]+)', line)

        if self.is_cygwin:
            guid_str = m.group(2)
            guid_bytes = b''.join([bytes.fromhex(p)[::-1] for p in guid_str.split('-')])
        else:
            guid_bytes = None

        return int(m.group(1)), guid_bytes
    
    async def connect_upstream(self):
        (reader, writer) = await asyncio.wait_for(asyncio.open_connection(localhost_ip, self.port), 1)

        if self.is_cygwin:
            writer.write(self.guid)

            try:
                data = await asyncio.wait_for(reader.read(16), 1)
                if data != self.guid:
                    raise Exception('GUID not match')
            except:
                writer.close()
                raise

            pid = os.getpid()
            uid = os.geteuid()
            gid = os.getegid()

            print('local:', pid, uid, gid)

            byte_order = 'little'
            data = pid.to_bytes(4, byte_order)
            data += uid.to_bytes(4, byte_order)
            data += gid.to_bytes(4, byte_order)

            writer.write(data)

            data = await reader.read(12)
            pid = int.from_bytes(data[:4], byte_order)
            uid = int.from_bytes(data[4:8], byte_order)
            gid = int.from_bytes(data[8:], byte_order)
            
            print('remote:', pid, uid, gid)

        print('upstream connected')

        return reader, writer


    async def handle_connected(self, reader, writer):
        print('downstream connected')

        try:
            (upstream_reader, upstream_writer) = await self.connect_upstream()
        except Exception as e:
            writer.close()
            print('Connect to upstream failed', e)
            return

        async def handle_up():
            while True:
                data = await reader.read(config.downstream_buffer_size)
                if not data:
                    break
                upstream_writer.write(data)

            print('down closed')
            upstream_writer.close()

        async def handle_down():
            while True:
                data = await upstream_reader.read(config.upstream_buffer_size)
                if not data:
                    break
                writer.write(data)

            print('up closed')
            writer.close()

        await asyncio.gather(handle_up(), handle_down())
        print('closed')

def build_config():
    class ProxyAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            proxies = []
            for value in values:
                src_dst = value.partition(':')
                if src_dst[1] == '':
                    raise parser.error('Unable to parse sockets proxy pair "%s".' % value)
                proxies.append([src_dst[0], src_dst[2]])
            setattr(namespace, self.dest, proxies)

    parser = argparse.ArgumentParser(
        description='Transforms Cygwin/msysgit compatible sockets to Unix sockets for the Windows Linux Subsystem.')
    parser.add_argument('--daemon', action='store_true')
    parser.add_argument('--cygwin', action='store_true',
                        help="Is cygwin or msysgit socket file")
    parser.add_argument('--downstream-buffer-size', default=8192, type=int, metavar='N',
                        help='Maximum number of bytes to read at a time from the Unix socket.')
    parser.add_argument('--upstream-buffer-size', default=8192, type=int, metavar='N',
                        help='Maximum number of bytes to read at a time from the Cygwin socket.')
    parser.add_argument('--pidfile', default='/tmp/cygwin2unix-socket.pid', metavar='FILE',
                        help='Where to write the PID file.')
    parser.add_argument('proxies', nargs='+', action=ProxyAction, metavar='source:destination',
                        help='A pair of a source Cygwin and a destination Unix sockets.')
    return parser.parse_args()

def daemonize():
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit()
    except OSError:
        sys.stderr.write('Fork #1 failed.')
        sys.exit(1)

    os.chdir('/')
    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit()
    except OSError:
        sys.stderr.write('Fork #2 failed.')
        sys.exit(1)

    sys.stdout.flush()
    sys.stderr.flush()

    si = open('/dev/null', 'r')
    so = open('/dev/null', 'a+')
    se = open('/dev/null', 'a+')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    pid = str(os.getpid())
    with open(config.pidfile, 'w+') as f:
        f.write('%s\n' % pid)

def cleanup():
    try:
        for pair in config.proxies:
            if os.path.exists(pair[1]):
                os.remove(pair[1])
        if os.path.exists(config.pidfile):
            os.remove(config.pidfile)
    except Exception as e:
        sys.stderr.write('%s' % (e))

if __name__ == '__main__':
    config = build_config()

    if os.path.exists(config.pidfile):
        # Check if process is really running, if not run cleanup
        with open(config.pidfile) as f:
            line = f.readline().strip()

        if PidExists(int(line)):
            # sys.stderr.write('%s: Already running (or at least pidfile "%s" already exists).\n' % (sys.argv[0], config.pidfile))
            sys.exit(0)
        else:
            cleanup()

    if config.daemon:
        daemonize()

    def run_servers():
        tasks = []
        for pair in config.proxies:
            server = ForwardServer(config.cygwin, pair[0])
            tasks.append(asyncio.start_unix_server(server.handle_connected, pair[1]))
        
        return asyncio.gather(*tasks)

    loop = asyncio.get_event_loop()
    servers = loop.run_until_complete(run_servers())

    print('Servers started.')

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    print('Closing servers')
    for server in servers:
        server.close()

    loop.run_until_complete(asyncio.gather(*[server.wait_closed() for server in servers]))
    loop.close()

    cleanup()
