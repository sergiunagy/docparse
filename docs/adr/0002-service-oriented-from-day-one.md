# Service-oriented architecture from day one

`docparse` is built as a set of independently deployable services (client/UI, gateway,
ingestion, extraction, AI Service, document store, Auth Service) from the very first
prototype, rather than starting as a modular monolith and splitting later. Inter-service
interfaces default to REST/HTTP for now, with the concrete interface and sync-vs-async
model treated as a dedicated architecture activity, not fixed here.

**Why:** the intended end state is service-oriented, and building it this way from the
start avoids a later monolith-to-services rewrite; it allows placing services
independently (e.g. UI or a routing service in the cloud, the GPU-bearing AI Service
local), swapping individual service-components, and outsourcing development of individual
services. Learning/experimentation with SOA is an explicit secondary goal of the project.

**Considered options:** (a) modular monolith for the MVP, split later; (b) modular monolith
plus a separately-deployable AI Service; (c) full SOA from day one. We chose (c).

**Consequences:** we deliberately accept higher upfront operational complexity
(inter-service contracts, multiple deployables, distributed debugging) that a single-family
MVP would not otherwise need. This is a conscious trade of speed-to-MVP for architectural
flexibility and learning, appropriate because experimentation is a stated goal.
