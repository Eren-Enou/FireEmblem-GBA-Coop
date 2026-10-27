# Internet-play path and first remote pilot

Status: optional verified TLS transport is implemented; **Internet play on two
PCs has not been verified**. This document defines a route and acceptance gates,
not a production-security or NAT-connectivity claim. The existing loopback TCP
launcher remains available. Tactical protocol v1 and LT authority are unchanged.

## Implemented transport boundary

`app/coop/security.py` uses standard Python SSL contexts: TLS 1.2 or newer,
required certificate validation and expected server-name checking. A client
finishes TLS verification **before** sending its army token. The host must provide
a certificate, its private key and an expected certificate name together. Remote
plaintext listeners and remote plaintext invitations reject. The local plaintext
client also checks its actual peer address, not just the requested hostname.
See the [Python SSL documentation](https://docs.python.org/3.12/library/ssl.html)
for context/certificate semantics; transport behavior is additionally tested here.

The setup helper creates a short-lived, dedicated self-signed development trust
anchor/server certificate. Its public certificate travels in each private JSON
invitation alongside the endpoint, expected name and army capability. Share the
correct army's invitation through an already trusted private channel; replacing
an invitation can replace both identity and capability. The private key remains
on the host. No trust-on-first-use prompt or insecure verification bypass exists.
Normal certificate date/hostname/chain checks remain enabled.

This is server identity plus bearer-token army authentication, not mutual TLS,
accounts, anti-cheat against a malicious host, revocable persistent identities or
a public matchmaking service. Host restart creates new army tokens; invitations
from the previous session no longer work. The development certificate expires
after seven days by default; use synchronized clocks and issue a new identity in
a new directory when needed. Keep identity keys/invitations out of Git. Windows
ACL hardening and token delivery UX remain to be implemented.

## Connectivity choice

| Route | Work needed | Decision |
| --- | --- | --- |
| Private overlay VPN + application TLS | Both PCs join a controlled private network; host advertises its reachable VPN address; restrict access to those devices | Recommended first two-PC pilot; no in-game NAT/relay implementation needed |
| Direct TLS host | Reachable host IP/DNS, inbound firewall rule and usually router configuration; some ISP topologies cannot accept inbound connections | Later opt-in pilot after hardening; no router/OS changes are made by this project |
| Dedicated public relay/host | Operated service, credentials, capacity, abuse controls and monitoring | Later accessibility work; do not substitute an unauthenticated arbitrary TCP forwarder |

For example, Tailscale documents direct connections and relay fallback when
direct connectivity cannot be established. That makes a private overlay a
practical first experiment, not proof that a particular user's network works.
[Official connection-type documentation](https://tailscale.com/docs/reference/connection-types).
No provider is installed, account created, pricing assumption made, or firewall
changed by this milestone. A provider/account decision belongs to the two players.

## Reproducible TLS localhost check

OpenSSL CLI is needed **only to generate a development identity and run TLS
certificate tests**. Game transport uses Python's standard `ssl` library. The
helper accepts `--openssl PATH` if it is not on PATH; the test suite expects it
on PATH. No new Python package is required.

From the repository root:

```powershell
.venv\Scripts\python.exe utilities/create_tls_identity.py --server-name localhost --output-dir artifacts/tls
.venv\Scripts\python.exe run_network.py host --tls-cert artifacts/tls/server-cert.pem --tls-key artifacts/tls/server-key.pem --server-name localhost
```

Then launch the same Blue and Green client commands in two other terminals:

```powershell
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

TLS options are embedded in the invitation; the client interface shows the
negotiated TLS version. The identity helper refuses to overwrite existing keys.
Reuse the existing identity while valid, or choose a new output directory.
Automated, ephemeral identities and a full three-process game check:

```powershell
.venv\Scripts\python.exe utilities/smoke_network.py --tls
.venv\Scripts\python.exe -m unittest app.tests.test_network_tls -q
```

## First private two-PC pilot — requires real players/network access

Use a reachable **private VPN address** on the hosting PC. Generate a certificate
with a stable expected name such as `two-banners.local` (the name is verified from
the trusted invitation; it need not resolve when the endpoint is an IP address).
Bind only the desired interface, or explicitly advertise a reachable address
when binding a wildcard. Example addresses below are placeholders, not tested
endpoints; replace them with that PC's actual address:

```powershell
.venv\Scripts\python.exe utilities/create_tls_identity.py --server-name two-banners.local --output-dir artifacts/pilot-tls
.venv\Scripts\python.exe run_network.py host --bind 100.100.100.10 --advertise-host 100.100.100.10 --tls-cert artifacts/pilot-tls/server-cert.pem --tls-key artifacts/pilot-tls/server-key.pem --server-name two-banners.local
```

The local Blue client also connects to that advertised VPN endpoint. Privately
transfer **only** `green.json` to the friend (not `blue.json` or the host key).
They run the same client command against their local copy. Their firewall/private
network policy must permit the chosen host port from the intended peer. If the
connection fails, investigate reachability separately from certificate/name/date
errors; never “fix” it by disabling verification or changing to remote plaintext.

Record this gate's evidence in PROGRESS.md:

1. Two distinct Windows PCs on different physical networks; exact commit and
   protocol version, endpoint route, seed and negotiated TLS version.
2. Initial matching revision/digest; each army moves, waits and attacks; Red acts;
   HP, inventory/durability, terminal outcomes and phase match at both clients.
3. Wrong name/untrusted identity rejected before token; wrong army credential and
   stale/duplicate commands rejected without simulation mutation.
4. Disconnect a player while idle and while a command resolves; both agree on
   the committed boundary, remaining player pauses, correct army can rejoin.
5. Test representative delay/jitter and stalled/abrupt connections. Record actual
   delay distributions, resolution times and timeout behavior rather than labels
   such as “lag tested.” No WAN results exist yet.

## Gates before opening a public service

- Review and update Python/OpenSSL and project dependency patch levels for the
  deployment; the recorded local development environment is not a production
  security certification.
- Add bounded pre-auth connection capacity, authentication rate limits and
  operational per-peer admission controls. TLS alone does not prevent resource
  exhaustion or guessing/flood attempts.
- Add an application heartbeat/idle-failure policy and command-result deadlines.
  Current EOF detection is not a reliable quick detector for a silent WAN loss.
- Bound/reschedule long engine resolution so network liveness is not held up by
  animations, AI, scripted events or unexpected prompts; preserve one authority.
- Provide certificate/token rotation, explicit invitation expiry/revocation,
  host identity UX, Windows private-file ACL handling and redacted diagnostics.
- Test transport downgrade attempts, bad identities, slow readers, half-open
  connections, reconnect storms and malformed traffic under load.
- Choose a NAT/connectivity route with real two-PC evidence. No STUN/TURN, relay
  infrastructure, automatic port forwarding or automatic reconnect is implemented.

The next product work is the private two-PC pilot and the liveness/admission
slice. Then implement the [campaign-save and tactical-parity methods](CAMPAIGN_AND_PARITY.md)
in tested increments. Full campaign saves and tactical parity are not enabled by
the TLS feature.
