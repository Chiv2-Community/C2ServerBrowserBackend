# Unofficial Chivalry 2 Server Browser

Currently things are not set up in the best way.  

`client` is a VisualStudio 2022 (Community Edition) project and should open pretty seamlessly with that. The build is a little messy. Somebody please help
`server` is a python poetry project

### Current Status

Server provides a basic game server listing api which requires a heartbeat every ~60 seconds to keep the server in the list

Client does nothing right now except list servers from a given host. Needs lots of work on the UI, and to actually get the core function going.  

The client's api code was generated using refitter 0.6.0 and https://raw.githubusercontent.com/Chiv2-Community/chivalry2-unofficial-server-browser/main/server/assets/chiv2-server-browser-api.yaml

### Project Layout

* [client](./client) contains the WPF windows client
* [server](./server) contains the server backend used to host server listings

For more info on the specific sub-projects, check out their respective directories.

### TO-DO

* Project Organization
* Create ServerListing models in the client for use in the DataGrid
    * Shouldn't show all fields, only name, ip, ping, current/max players, and current map
    * Should also contain description and mods list for display in a text box to the right of the DataGrid
* Convert `Server` api outputs to the ServerListing models 
* Add a `connect` button.
    * This app will replace the launcher app and forward any CLI params to the actual game executable + a command to join the selected server
