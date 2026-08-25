# Authentication is a separate, likely-outsourced service

Authentication is its own Service (the Auth Service), not a module folded into the gateway
or the application, and the identity provider behind it is expected to be outsourced to a
third party (e.g. a hosted auth provider) rather than hand-built.

**Why:** isolating auth behind its own service lets us adopt (and later change) an external
identity provider without touching the rest of the application, which suits an early-stage
project that may outsource auth rather than implement and maintain it. It also keeps the
security-sensitive surface in one swappable place. This follows from the service-oriented
decision (ADR-0002).

**Consequences:** how much auth is actually needed, and which provider, depend on the
deployment posture (LAN-only vs public endpoint), which is being decided by a separate
prototype; this ADR fixes only the boundary (auth is its own service and outsource-ready),
not the provider choice.
