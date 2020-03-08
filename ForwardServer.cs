using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Diagnostics;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Net;
using System.Net.Sockets;

namespace ForwardUnixSocket
{
    class ForwardServer
    {
        private static readonly Regex pattern = new Regex(@"(?<=>)\d+(?=\s)");
        private readonly TcpListener listener;

        public int upstreamPort;

        public ForwardServer(string socketPath)
        {
            upstreamPort = GetUnixSocketPort(socketPath);
            listener = new TcpListener(IPAddress.Any, upstreamPort);
        }

        private static int GetUnixSocketPort(string socketPath)
        {
            string lines = File.ReadAllText(socketPath);
            var m = pattern.Match(lines);

            return int.Parse(m.Value);
        }

        public void Run()
        {
            listener.Start();
            Console.WriteLine("Listening on {0}", listener.LocalEndpoint);

            while (true)
            {
                var client = listener.AcceptTcpClient();
                Task.Run(() => HandleConnection(client));
            }
        }

        private async void HandleConnection(TcpClient client)
        {
            var clientEndPoint = client.Client.RemoteEndPoint;
            Console.WriteLine("Downstream connected: {0}", clientEndPoint);

            using (client)
            {
                using (var localClient = new TcpClient())
                {
                    try
                    {
                        await localClient.ConnectAsync(IPAddress.Loopback, upstreamPort);
                    }
                    catch (Exception e)
                    {
                        Console.WriteLine("Connect to upstream failed: {0}", e.Message);
                        return;
                    }

                    Debug.Print("Upstream connected");

                    var upstream = localClient.GetStream();
                    var downstream = client.GetStream();

                    await Task.WhenAll(CopyStream(upstream, downstream), CopyStream(downstream, upstream));

                }
            }

            Console.WriteLine("Closed");
        }

        private async Task CopyStream(NetworkStream source, NetworkStream dest)
        {
            try
            {
                await source.CopyToAsync(dest);
            }
            catch (ObjectDisposedException)
            {
                Debug.Print("Local close");
            }
            catch (Exception e)
            {
                Console.WriteLine("Connection exception: {0}", e.Message);
            }
            finally
            {
                dest.Close();
                Debug.Print("Connect close");
            }
        }
    }
}
