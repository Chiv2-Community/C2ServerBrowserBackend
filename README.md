# Unofficial Chivalry 2 Server Browser

### Current Status

Server provides a basic game server listing api which requires a heartbeat every ~60 seconds to keep the server in the list

Client does nothing right now except list servers from a given host. Needs lots of work on the UI, and to actually get the core function going.  

The client's api code was generated using refitter 0.6.0 and https://raw.githubusercontent.com/Chiv2-Community/chivalry2-unofficial-server-browser/main/server/assets/chiv2-server-browser-api.yaml

### Project Layout

* [client](./client) contains the WPF windows client
* [server](./server) contains the server backend used to host server listings

For more info on the specific sub-projects, check out their respective directories.
