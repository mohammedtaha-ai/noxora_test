# ADR-005: العقود العابرة للغات

**الحالة:** Accepted as target contract strategy; transport/service implementation deferred.  
**التاريخ:** 2026-08-23.

## السياق

يتطلب target Laravel/PHP وGo وPython وC#/Unity عقودًا تمنع DTO drift وdatabase coupling. لكن ليس كل boundary يحتاج gRPC، ولا يجوز أن نستبدل transport S0 HTTP/JSON loopback المثبت من أجل target cloud لم ينفذ. تحتاج الأحداث إلى schema/versioning قابلة للنقل ولا يمكن أن تظل Python dataclasses كـcross-language source of truth.

## القرار

| boundary | selected/target contract | rationale | explicit limit |
|---|---|---|---|
| public product/control API | HTTPS REST/JSON | conventional user/admin/resource API، inspectable، Laravel-compatible | ليس hot physiology transport. |
| S0 local client transport | HTTP/JSON loopback + existing client DTOs | مثبت محليًا ومحدود purpose | لا يستبدل الآن ولا يصبح cloud auth API. |
| future realtime client | WebSocket via Go realtime/platform layer when justified | bidirectional session projection/commands with reconnect/routing boundary | لا Unity→Pulse أو client clock/truth. |
| Laravel ↔ Go internal | gRPC/Protobuf candidate for allocation/grant/query command boundary; REST allowed initially if simpler | typed generated contracts across PHP/Go وversioning potential | لا codegen/service until contract spike/CI. |
| Go ↔ Python worker | gRPC/Protobuf candidate when worker is remote/process boundary | typed session command, route, lease generation, safe projection/events | لا raw Pulse/internal state أو Python business-table write. |
| Go ↔ Go | gRPC/Protobuf candidate only after extraction | typed operational APIs/streaming where value proven | لا microservices by default. |
| cross-language event | canonical names/version + portable JSON Schema envelope now; evaluate Protobuf/Avro with broker trigger | human inspectability/current JSON contracts and broker path | Python dataclass is never canonical event schema. |

Protocol Buffers are language- and platform-neutral, generate bindings across the target languages, and support additive schema evolution; gRPC documents support for PHP, Go, Python, C#, and C++.[1] [2] That capability supports a **candidate** internal contract strategy, not automatic use for public APIs or all internal calls.

## contract governance

1. Store future `.proto`, JSON schemas, event naming registry, generated-code configuration, and compatibility fixtures under a language-neutral `/contracts` ownership boundary only after an ADR-approved migration.
2. Maintain one canonical semantic name/version strategy. `event_type` + `schema_version` remain portable; routing/order stay scoped to `routing_key`, not global.
3. Add fields compatibly; never reuse Protobuf tags, change field types, or conflate storage messages with RPC messages. Reserve removed tags/names.[3]
4. Versioned schemas contain IDs, tenant/session correlation, classification, and minimal payload. They exclude secrets, raw client tokens, PII without explicit policy, artifact bytes, and Pulse internals.
5. Generated clients are artifacts of contract CI, not hand-maintained cross-language DTO copies. Compatibility tests include old producer/new consumer and new producer/old consumer cases before a production rollout.

## authorization context contract

Laravel authorizes business intent and mints/requests a short-lived scoped session grant. Go validates that context using a trusted issuer/service identity and binds it to `principal_id`, `tenant_id`, `session_id`, command scope, expiry, audience, request/correlation ID. Python accepts only trusted internal Go command/context.

The grant contract never treats arbitrary `tenant_id` supplied by Unity/web as authority. This ADR does not build JWT/OIDC/SSO/token issuance; a future security ADR must define signatures, rotation, revocation, service credentials, replay defenses, audit, and threat model.

## event/outbox strategy

Each authoritative owner atomically commits its state mutation and its own immutable outbox record. Relay delivery is at-least-once; consumers deduplicate `event_id`; post-publish crashes can cause duplicate delivery. Analytics/AI are derived and asynchronous. A slow consumer or ClickHouse/queue outage cannot be in VPE's progression path.

## alternatives rejected

| alternative | reason |
|---|---|
| Python dataclasses as cross-language contract | no PHP/Go/C# canonical schema/codegen/evolution source. |
| direct cross-service SQL | violates ADR-004 ownership and makes schemas hidden APIs. |
| REST for all internal high-value streaming contracts | may be viable for simple early calls, but leaves no typed streaming/codegen path where value is proven. |
| gRPC for every public/client call | worsens browser/client interoperability and hides conventional resource API needs. |
| replace local S0 HTTP/JSON now | violates proven bounded transport and adds unneeded risk. |
| schema-free event JSON | permits drift and prevents reliable compatibility review. |
| AI synchronous in live path | latency/failure/authority violate simulation invariants. |

## consequences

No Protobuf files, codegen, Laravel app, Go service, WebSocket, SQS, Kafka, or broker is added in this batch. The next approved implementation should start with a narrow contract proof and compatibility CI—not framework scaffolding. Existing `PlatformEvent` Python class stays test/reference code that must conform to the documented envelope until a language-neutral schema becomes canonical.

## references

[1]: https://protobuf.dev/overview/ "Protocol Buffers: Overview"
[2]: https://grpc.io/docs/languages/ "gRPC: Supported languages"
[3]: https://protobuf.dev/best-practices/dos-donts/ "Protocol Buffers: Best Practices"
[4]: ../contracts/platform-event-envelope-v0.1.md "Nexora Platform Event Envelope"
[5]: ../architecture/polyglot-data-and-deployables-v0.1.md "Nexora Polyglot Data Ownership and Deployables"
