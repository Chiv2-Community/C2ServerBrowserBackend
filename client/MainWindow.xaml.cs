using Refit;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.DirectoryServices.ActiveDirectory;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;

namespace Chivalry2UnofficialServerBrowser
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {


        public MainWindow()
        {
            InitializeComponent();
            Chiv2ExeArgs.Text = string.Join(" ", Environment.GetCommandLineArgs().Skip(1));
        }

        private void TextBox_TextChanged(object sender, TextChangedEventArgs e)
        {

        }

        private void DataGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {

        }
        private void ConnectButton_Click(object sender, RoutedEventArgs e) {

            var selectedServer = ServerListGrid.SelectedItem as ServerTableElement;
            if(selectedServer == null)
            {
                MessageBox.Show("Please select a server to connect to.");
                return;
            }

            var cliArgs = new List<string>();

            var startInfo = new ProcessStartInfo();

            var exePath = Chiv2ExePath.Text;
            cliArgs.Add(selectedServer.Address);
            cliArgs.Add(Chiv2ExeArgs.Text);

            var proc = new Process();
            startInfo.FileName = exePath;
            startInfo.Arguments = string.Join(" ", cliArgs);
            proc.StartInfo = startInfo;
            proc.Start();
        }

        private void RefreshButton_Click(object sender, RoutedEventArgs e)
        {
            var client = RestService.For<Chivalry2UnofficialServerBrowser.IServerBrowserAPI>("http://" + ServerBrowserHost.Text);
            var responseServers = client.ServersGET().Result.Servers;
            var serverList = new List<ServerTableElement>();
            foreach (var server in responseServers)
            {
                serverList.Add(new ServerTableElement
                {
                    Name = server.Name,
                    Address = server.Ip_address + ":" + server.Port,
                    Map = server.Current_map,
                    Players = server.Player_count + " / " + server.Max_players,
                    Ping = "N/A",
                    Mods = server.Mods,
                    Description = server.Description
                });
            }

            UpdateServerList(serverList, true);
        }

        private async void UpdateServerList(ICollection<ServerTableElement> elems, bool shouldPing)
        {
            ServerListGrid.Items.Clear();
            var pingTasks = new List<Task>();
            foreach (var elem in elems)
            {
                ServerListGrid.Items.Add(elem);
                if (shouldPing)
                    pingTasks.Add(elem.UpdatePingAsync());
            }

            while (pingTasks.Count > 0)
            {
                var finishedTask = await Task.WhenAny(pingTasks);
                ServerListGrid.Items.Refresh();
                pingTasks.Remove(finishedTask);
            }
        }

    }
}
