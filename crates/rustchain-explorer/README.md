<!-- SPDX-License-Identifier: MIT -->
# rustchain-explorer

A read-only RustChain CLI for node health, current epochs, miner hardware and
wallet balances. It accepts wallet aliases as well as RTC addresses, requires no
private keys, verifies TLS certificates, and preserves node fields in JSON output.

## Local installation and use

This crate is prepared for publication but has **not been published** by this
change. From this directory, with stable Rust installed:

```sh
cargo install --path . --locked
rustchain-explorer health
rustchain-explorer epoch
rustchain-explorer miners
rustchain-explorer balance vintage-miner
rustchain-explorer --json balance "wallet with spaces"
rustchain-explorer --node https://rustchain.org --timeout 10 --json epoch
```

After a separately authorized crates.io release, installation will be
`cargo install rustchain-explorer --locked`.

Global flags work before or after the subcommand. `--node` accepts an HTTP(S)
origin, including a port, without credentials, a path, query or fragment.
Timeouts are 1–300 seconds (default 15). Nodes requiring an untrusted certificate
must be served through a trusted endpoint. Redirects are reported as errors.

| Command | GET endpoint |
| --- | --- |
| `health` | `/health` |
| `epoch` | `/epoch` |
| `miners` | `/api/miners` |
| `balance WALLET` | `/wallet/balance?miner_id=WALLET` (URL encoded) |

Default output has a heading and labeled JSON values. `--json` emits the complete
response, so scripts can select fields without losing newly added node fields:

```sh
rustchain-explorer --json epoch | jq '.epoch'
rustchain-explorer --json miners | jq '.miners[] | .miner'
rustchain-explorer --json balance vintage-miner | jq '.amount_i64'
```

Amounts are not converted through a floating-point arithmetic layer; use the
node's integer `amount_i64` field for exact accounting. The miner response may be
an object containing `miners` or a top-level array; JSON mode preserves either.
Exit codes: 0 success, 1 network/HTTP/JSON/node/output failure, 2 invalid arguments.
Diagnostics go to stderr. Health `ok: false` and non-null `error` fields are
failures even when HTTP returns 200.

## Compatibility and bounty scope

This implements the explorer CLI idea in
[bounty #726](https://github.com/Scottcjn/rustchain-bounties/issues/726).
The live node at `https://rustchain.org` was inspected on 2026-10-04: health uses
`ok`/`uptime_s`, miners use `miner`/`antiquity_multiplier`, and balances use
`amount_i64`/`amount_rtc`. The published `rustchain-client` 0.1.0 instead requires
`status`, `wallet` (or `miner_id`), and `balance`, respectively. This binary uses
reqwest directly to preserve the current API contract without modifying that
crate or creating another general-purpose client library.

Duplicate checks found no `rustchain-explorer` crate on crates.io, no Rust
explorer in upstream's full main tree (including no `crates/` directory), and no
competing open Rust explorer PR in Rustchain or rustchain-bounties. Existing web
explorers are separate applications. `rtc-types` already has a submission in the
bounty comments, `rustchain-client` and `rustchain-wallet` are published, and
`bottube-client` has a published submission. The existing `rustchain-address`
[PR #8557](https://github.com/Scottcjn/Rustchain/pull/8557) is outside this change.
Availability checks are point-in-time observations, not a reserved reward.

This is a self-contained Cargo project at `crates/rustchain-explorer` in the
Rustchain repository, not a nested Git repository. Publication and crates.io
release remain separately authorized external actions. No claim of publication,
docs.rs hosting or passing remote CI is made here.

## Validation

Run from this crate directory:

```sh
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo doc --locked --no-deps
cargo package --locked
```

On Windows, a deeply nested checkout can exceed the MSVC linker's path limit.
Set `CARGO_TARGET_DIR` to a shorter build directory inside the checkout if the
default `target/` directory fails to link. All dependencies are pinned in
`Cargo.lock`, so validation also works with Cargo's `--offline` flag once they
have been fetched once.

Integration tests execute the real binary against a local HTTP server and cover
all endpoint paths, current response shapes, query encoding, output modes, HTTP
and application errors, malformed JSON, argument validation and connection errors.
They do not contact the public node. A manual live smoke check is:

```sh
cargo run --locked -- --json health
cargo run --locked -- --json epoch
cargo run --locked -- --json miners
cargo run --locked -- --json balance example
```

## License

MIT; see [LICENSE](LICENSE). Rust source files carry SPDX identifiers.
