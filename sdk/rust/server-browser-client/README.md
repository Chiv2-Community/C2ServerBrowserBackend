# server-browser-client

Generated async HTTP bindings for the backend OpenAPI contract. Use
`server-browser-client-sdk` for registration lifecycle management.

Await every operation from an application-owned Tokio runtime with I/O enabled.
Configuration construction does not create a runtime. Default clients disable
redirects; injected clients retain their caller's policy.

Credentials are explicit operation arguments. Caller-supplied clients own their
timeout, redirect, proxy and source-address policy. Errors can contain response
bodies; do not log them when responses may contain credentials.
