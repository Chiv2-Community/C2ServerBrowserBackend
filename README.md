# Unofficial Chivalry 2 Server Browser

Currently things are not set up in the best way.  

`client` is a VisualStudio 2022 (Community Edition) project and should open pretty seamlessly with that.
`server` is a simply python poetry project, though the config isn't fully working. It's a fairly simple setup and easy to get running if you have any familiarity with python though.

Sorry for the mess. I will clean things up soon.

### Current Status

Server provides a basic game server listing api which requires a heartbeat every ~60 seconds to keep the server in the list

Client does nothing right now except list servers from a given host. Needs lots of work on the UI, and to actually get the core function going.  

The client's api code was generated using refitter 0.6.0 and https://raw.githubusercontent.com/Chiv2-Community/chivalry2-unofficial-server-browser/main/server/assets/chiv2-server-browser-api.yaml