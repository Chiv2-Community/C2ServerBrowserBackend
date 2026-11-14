# server-browser-client

Generated blocking HTTP bindings for the backend OpenAPI contract. Use
`server-browser-client-sdk` for registration lifecycle management.

Credentials are explicit operation arguments. Caller-supplied clients own their
timeout, redirect, proxy and source-address policy. Errors can contain response
bodies; do not log them when responses may contain credentials.
