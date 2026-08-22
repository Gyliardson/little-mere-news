# Harvester outbound feed trust boundary

External RSS/Atom feeds are untrusted network inputs. The Harvester applies a default-deny destination policy to the **feed-fetch transport only**; the separately configured Ollama endpoint is an intentional local-service boundary and is not governed by this external-feed policy.

For every configured feed URL and every redirect hop, the Harvester requires:

- absolute `http` or `https` URL;
- no embedded URL credentials;
- successful hostname resolution;
- every resolved address to be globally routable according to Python's `ipaddress` classification;
- the actual TCP connection to be pinned to one of those already-approved IP addresses rather than resolving the hostname again inside the HTTP client;
- HTTPS certificate verification and SNI against the original hostname while the socket connects to the pinned IP;
- manual redirect handling with each `Location` resolved, validated and separately pinned before contact;
- at most five redirects;
- bounded source timeouts/retries and a 5 MiB response-size safety limit.

Consequently, external feeds fail closed when a target resolves to loopback, RFC1918/private, link-local, unspecified, multicast/reserved or other non-global address space, including IPv6 equivalents. This includes common link-local metadata destinations such as `169.254.169.254`. A public endpoint that redirects to an internal/private destination is rejected before that destination is contacted.

Pinning the socket destination closes the DNS time-of-check/time-of-use gap that exists when code validates one DNS answer and then asks a normal HTTP client to resolve the hostname again. DNS may legitimately change between separate requests or redirect hops; each request uses only the address set validated for that specific request.

The repository does not implement a private-feed bypass or implicit allowlist. If private feeds ever become a real product requirement, they must use an explicit reviewed opt-in policy rather than weakening the default external-feed boundary.

DNS resolution failure, forbidden destinations, malformed redirects, redirect loops/overflow, oversized responses and transport failures are isolated to the affected feed and use the existing bounded retry behavior. Tests inject deterministic DNS and HTTP doubles; critical CI does not need live DNS or real external feeds.

This policy materially reduces SSRF exposure but does not turn arbitrary network access into a trusted capability. Deployment-level egress controls remain useful defense in depth where available.
