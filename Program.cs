using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Text;
using System.Threading.Tasks;

namespace ForwardUnixSocket
{
    class Program
    {
        static void Main(string[] args)
        {
            if (args.Length == 0)
            {
                Console.WriteLine("Missing socket file path.");
                return;
            }

            var ip = GetWslIp();
            Console.WriteLine("WSL IP: {0}", ip);

            var server = new ForwardServer(ip, args[0]);
            server.Run();
        }

        static IPAddress GetWslIp()
        {
            var interfaces = NetworkInterface.GetAllNetworkInterfaces();
            foreach (var i in interfaces)
            {
                if (!i.Name.Contains("WSL"))
                {
                    continue;
                }

                var addresses = i.GetIPProperties().UnicastAddresses;
                foreach (var a in addresses)
                {
                    if (a.Address.AddressFamily != System.Net.Sockets.AddressFamily.InterNetwork)
                    {
                        continue;
                    }

                    return a.Address;
                }
            }

            return null;
        }
    }
}
