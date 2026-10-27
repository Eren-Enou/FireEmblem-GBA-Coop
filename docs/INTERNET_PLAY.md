# Private Internet play and the first two-PC test

Phase 3A is locally verified: TLS, authenticated armies, liveness detection,
bounded admission/rates, live-host rejoin and complete network battles.
**Actual two-PC Internet connectivity remains unverified.** The physical remote
playtest is a separate human acceptance gate. No firewall, router, account,
external service or public port configuration was changed during development.

## Connectivity choice and trust

Use a private overlay/VPN already configured for the two intended Windows PCs,
plus the game's verified TLS. An overlay avoids implementing NAT traversal or a
relay in this milestone. For example, the existing evaluation refers to
[Tailscale's connection types](https://tailscale.com/docs/reference/connection-types):
direct connections and provider relay fallback are connectivity options, not
proof that these particular PCs can connect. Service selection, installation,
accounts and OS/network-policy changes require the users' separate decision.
Direct public hosting and a public relay/matchmaking service remain out of scope.

TLS verifies the host certificate and expected name **before** the army token is
sent. Remote plaintext is rejected. Invitations contain the endpoint, public
trust certificate, expected name and a bearer capability for exactly one army.
Deliver them through an already trusted private channel. Replacing an invitation
can replace both trust and credentials. Never send the host's private key or
Blue's invitation to the Green player. Never disable certificate verification.
See the [network contract](NETWORK_PROTOCOL.md) and
[Python SSL documentation](https://docs.python.org/3.12/library/ssl.html).

## Prepare both Windows PCs

1. Use an already configured private overlay restricted to the intended devices.
   Determine the hosting PC's reachable private overlay IP. Bind only that IP for
   this pilot; do not expose a public listener or change router/firewall settings
   as a workaround.
2. On each PC clone [the project](https://github.com/Eren-Enou/FireEmblem-GBA-Coop),
   or update its existing checkout. Compare `git rev-parse HEAD`: use the same
   current protocol-v5 commit on host and both clients. Protocol v5 includes healing choices, weapon XP/mana and ping/pong controls; old clients must
   update.
   Keep the inherited development resources present; do not create an
   unauthorized game-asset bundle for the other player.
3. From the repository root, create the environment if it does not exist:

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements_editor.txt
   .venv\Scripts\python.exe -c "from app.engine.codegen import source_generator; source_generator.generate_all()"
   ```

4. The host needs an existing OpenSSL CLI to generate a development identity.
   The helper accepts `--openssl "C:\path\to\openssl.exe"` if necessary. The
   ordinary remote client needs no OpenSSL CLI; transport uses Python `ssl`.
   Correct both clocks before TLS verification.

## Start host and clients

The address `100.100.100.10` below is a **placeholder**, not a tested endpoint.
Replace both occurrences with the host's actual reachable private overlay IP.
The certificate name need not resolve when the invitation connects to an IP.

On the host, from the repository root:

```powershell
.venv\Scripts\python.exe utilities/create_tls_identity.py --server-name two-banners.local --output-dir artifacts/pilot-tls
.venv\Scripts\python.exe run_network.py host --bind 100.100.100.10 --advertise-host 100.100.100.10 --tls-cert artifacts/pilot-tls/server-cert.pem --tls-key artifacts/pilot-tls/server-key.pem --server-name two-banners.local --seed 1
```

The identity helper refuses overwrites. Reuse an existing valid identity or use
another output directory. The dedicated development certificate expires after
seven days by default (helper allows 1-30 days). Keep the key only on the host.
Windows chmod is not a complete ACL policy; keep the folder private to your user.

Wait for `HOST_READY`. Keep that terminal open. In a second host terminal:

```powershell
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
```

Privately transfer **only** `artifacts/network/green.json` to the friend. They
place it in their own ignored `artifacts/network/` directory and run:

```powershell
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

Blue should show `You: BLUE`, the friend `You: GREEN`, and both should show
TLSv1.2 or TLSv1.3, both connected seats, and matching turn/phase/revision/Check.
Host restart creates a fresh map and new invitations, invalidating old tokens.
There is no host-restart recovery. Stop the host with Ctrl+C after the session.

## Controls and a reproducible complete battle

Click your unit, then an outlined tile to **commit** a move. Click an outlined
Red token to attack with the selected weapon; number keys select inventory
weapons. W waits; E ends the army phase; R resynchronizes. Right-click/Escape
deselect. Selecting another army only inspects it. Gray units are finished.
Hover shows zero-based `(x,y)` coordinates. Selection shows HP, tile, movement,
weapon uses and attack choices. Green End resolves Red AI on the host before
publishing the next Blue boundary. Shared victory/defeat retains the final board.

The following seed-1 sequence is the automated winning baseline. Each attack
uses the unit's Iron Axe; these are tactical commands, not fixture modifications:

1. Turn 1: wait both Blue units, End; wait both Green units, End.
2. Blue turn 2: move Captain to `(5,2)`, attack Red 1; move Guard to `(5,4)`,
   finish Red 1; End.
3. Green turn 2: Guard attacks Red 2; move Captain to `(5,6)`, finish Red 2; End.
4. Blue turn 3: Guard attacks Red 3; move Captain to `(4,5)`, attack Red 3; End.
5. Green Captain finishes Red 3. Expect shared victory, revision **20**, turn **3**.

Different actions or seeds can change the result. On a separate fresh seed-1
host, both armies repeatedly ending their phases without acting produces shared
defeat at revision **6**, Blue turn **4**. Restarting the host requires privately
redistributing its new Green invitation before this separate test.

## Disconnect and rejoin

Close Green while idle: Blue pauses when GREEN disappears. Relaunch the same
Green invitation against the still-running host; it reclaims GREEN and receives
the latest completed state. Repeat while a command/Red AI resolves: that accepted
command finishes exactly once, then compare revision/Check after rejoin. There
is no automatic tactical replay. Never repeat an action with an unknown outcome.

The host challenges every five seconds and expires an unanswered challenge after
20 seconds (about 25 seconds from the last acknowledgment). The client closes
after 35 seconds without any host frame. A command pending for 120 seconds gives
an unknown-outcome warning and disconnects. Restore connectivity and manually
relaunch the same invitation to recover authoritative state. During resolution,
transport readers keep running between LT steps; peer status is published at
the next completed command boundary. A single stuck engine call is not preempted.

## Diagnose a failed connection

| Symptom | Check / action |
| --- | --- |
| Refused or timeout | Host is running; invitation IP is its current private overlay IP and port matches (default 38670); both devices are online in the private overlay. `Test-NetConnection <host-private-IP> -Port 38670` checks TCP reachability only. Review existing OS/private-network policy without automatic changes. |
| TLS name/CA/date failure | Use the original correct invitation, expected certificate name, valid certificate and correct clocks. After expiry, generate a new identity in a new directory and restart to regenerate invitations. Never disable validation. |
| authentication_failed | Invitation belongs to this live host. Restart invalidates previous tokens. Privately transfer the intended army invitation again. |
| seat_in_use | Close the old client or allow its heartbeat to expire, then relaunch. Do not substitute the other army token. |
| admission_limit / rate_limit / request_queue_full | Stop extra clients/scripts, wait for admission credits to replenish, relaunch. Simulation remains intact. |
| Missing peer / heartbeat timeout / host silence | Restore private connectivity and relaunch the same invitation while the host remains alive. |
| Stale-base rejection or Check differs | Wait for resolution, press R on each client, compare at rest. Automatic resync handles stale/digest rejection. Persistent mismatch: stop commands, keep redacted logs/commit/revisions for investigation. |
| Unknown command outcome | Rejoin for authoritative state; do not blindly replay. |
| Host resolution fault | Session freezes. Inspect host log; no crash save/rollback exists. Restart creates a fresh battle. |

Never paste invitation contents or private keys into reports. Report only commit,
army, phase/turn, revision/Check, transport, error code and redacted timestamps.

## Physical acceptance record - still unverified

Record results in [PROGRESS.md](PROGRESS.md) only after executing the remote test:

- Two distinct Windows PCs on different physical networks; same commit,
  protocol, private route, seed, TLS version and timing observations.
- Matching initial state, movement/wait/attack by both armies, repeated Red AI,
  HP/durability/death and a matching complete terminal outcome.
- Idle and resolution disconnect, pause, correct-army rejoin and matching state;
  representative delayed/abrupt/silent-loss behavior and measured timeout times.
- A certificate/name/credential failure closes safely; neither player can command
  the other army. Automated negative cases are in the local regression suite.

No two-PC, WAN latency/jitter, packet-loss or two-human mouse-play result has
been claimed by local automation.

## Remaining public-service gates

Application admission is now capped at eight post-TLS sockets, with a global
burst of 16/two new attempts per second. Authenticated peers have burst 30/ten
frames per second and a four-request queue. These are proportionate private
pilot controls. They do not cap simultaneous TLS handshakes or kernel backlogs.
Before public exposure, review those resources, slow readers/reconnect storms,
runtime/dependency patch levels and adversarial load. Heartbeats/result deadlines
need real WAN measurements. Individual engine calls and unsupported event prompts
need further audit before broader scenarios. Certificate/token expiry/revocation
UX, Windows ACL handling and durable recovery remain future work.

No public matchmaking, relay service, automatic port forwarding, VPN installation,
automatic reconnect loop or full tactical parity is implemented. Original campaign
chapter-boundary save/restart is implemented; see [CHECKPOINTS.md](CHECKPOINTS.md).
Future campaign work follows [CAMPAIGN_AND_PARITY.md](CAMPAIGN_AND_PARITY.md).
