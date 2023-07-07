using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Chivalry2UnofficialServerBrowser
{
    using System.Net.NetworkInformation;
    using System.Linq;
    using System.Threading.Tasks;

    public class ServerTableElement
    {
        public string Name { get; set; }
        public string Address { get; set; }
        public string Map { get; set; }
        public string Players { get; set; }
        public string Ping { get; set; }
        public ICollection<Mod> Mods { get; set; }
        public string Description { get; set; }

        // Update ping asynchronously
        public async Task UpdatePingAsync()
        {
            var address = Address.Split(':')[0];
            var ping = new Ping();

            try
            {
                var reply = await ping.SendPingAsync("google.com", 1000);
                Ping = reply.Status == IPStatus.Success ? reply.RoundtripTime.ToString() : "N/A";
            }
            catch
            {
                Ping = "Error";
            }
        }
    }
}
