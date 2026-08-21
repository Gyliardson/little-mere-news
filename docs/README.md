# Little Mere News technical documentation

This directory is the canonical index for Little Mere News engineering documentation. The root [README](../README.md) is the visitor-facing overview; the documents below describe security boundaries, reliability invariants, operational procedures, and assurance evidence in greater depth.

## Security

- [Outbound network security](security/OUTBOUND_NETWORK_SECURITY.md) — external RSS/Atom destination validation, redirect policy, DNS/socket pinning, response bounds, and the feed-fetch SSRF trust boundary.

## Reliability

- [Publisher queue ownership](reliability/PUBLISHER_QUEUE_OWNERSHIP.md) — immutable batch identity, Harvester claims, Publisher inbox/processing ownership, crash recovery, and replay safety.
- [Publisher retry policy](reliability/PUBLISHER_RETRY_POLICY.md) — structured transient-failure classification, bounded in-process/cross-run retry, deferred work, and fail-closed quarantine.

## Operations

- [Deployment and clean-room runtime contract](operations/DEPLOYMENT.md) — component boundaries, environment contracts, database bootstrap, optional Hyper-V/Ollama topology, production smoke verification, and residual operational risks.

## Assurance

- [Testing Little Mere News](assurance/TESTING.md) — deterministic frontend/Python/PostgreSQL/browser gates, accessibility scope, security checks, and the limits of CI evidence.

## Translations

Deep technical documentation remains canonical in English. The visitor-facing project overview is available in:

- [English](../README.md)
- [Português do Brasil](i18n/pt-BR/README.md)
- [日本語](i18n/ja/README.md)
- [Español](i18n/es/README.md)

## Evidence boundary

Little Mere News distinguishes repository-proven contracts from deployment-managed and external properties. Deterministic CI can establish source, queue, database, browser, dependency, and static-analysis properties for an exact candidate SHA. It does not by itself prove live production credentials, current third-party availability, production Supabase configuration, DNS/provider health, Hyper-V host state, or model/runtime provenance that was not actually exercised.

Documentation should keep those evidence domains explicit rather than turning a deployment convention or external assumption into an architectural guarantee.
