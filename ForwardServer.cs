using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Net;
using System.Net.Sockets;

namespace ForwardUnixSocket
{
    class ForwardServer
    {
        private static Regex pattern = new Regex(@"(?<=>)\d+(?=\s)");
        private TcpListener listener;

        public int upstreamPort;

        public ForwardServer(IPAddress ip, string socketPath)
        {
            upstreamPort = GetKeeAgentPort(socketPath);
            listener = new TcpListener(ip, upstreamPort);
        }

        private static int GetKeeAgentPort(string socketPath)
        {
            string lines = File.ReadAllText(socketPath);
            var m = pattern.Match(lines);

            return int.Parse(m.Value);
        }

        public void Run()
        {
            listener.Start();
            Console.WriteLine("Listening on {0}", upstreamPort.ToString());

            while (true)
            {
                var client = listener.AcceptTcpClient();
                Task.Run(() => HandleConnection(client));
            }
        }

        private async void HandleConnection(TcpClient client)
        {
            Console.WriteLine("Downstream connected");

            var localClient = new TcpClient();

            try
            {
                await localClient.ConnectAsync("localhost", upstreamPort);
            }
            catch (Exception e)
            {
                Console.WriteLine("Connect to upstream failed: {0}", e.Message);
                localClient.Close();
                return;
            }

            Console.WriteLine("Upstream connected");

            var upstream = localClient.GetStream();
            var downstream = client.GetStream();

            await Task.WhenAll(CopyStream(upstream, downstream), CopyStream(downstream, upstream));

            Console.WriteLine("Closed");
        }

        private async Task CopyStream(NetworkStream source, NetworkStream dest)
        {
            byte[] buf = new byte[4096];
            int count;

            while (true)
            {
                try
                {
                    count = await source.ReadAsync(buf, 0, buf.Length);
                    await dest.WriteAsync(buf, 0, count);
                }
                catch (Exception)
                {
                    //Console.WriteLine("Connect exception: {0}", e.Message);
                    break;
                }
            }

            dest.Close();
        }
    }
}
