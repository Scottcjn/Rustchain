# Beacon Atlas minimap verification

A focused corner overview for `site/beacon/`: green agent points, amber city centers,
and a cyan camera marker. It uses the real Atlas position getters, keeps camera movement
out of the overview bounds, clamps an off-map camera to the edge, caps redraws at 10 Hz,
and passes mouse/touch gestures through to the existing OrbitControls.

## Source and scope

This integrates the retained `RUSTCHAIN-1524-MINIMAP-ZSOL-20260917` source packet from
[the earlier controlled source publication](https://github.com/woahwhattheheck/rustchain-bounties/pull/84),
commit `efff70b53d0c8480d2999e110c4ee5d3e797e769`. Its original inspected upstream was
`aa584b344a766f6c0f8613ba7198d1cc7ffbae35`; this integration was checked against
`Scottcjn/Rustchain` main `5dc7a37d2334568e4424d5a80bc9af43f3c92906`.
The four retained model regressions remain, with the correct import path for the upstream
`tests/` directory. The runtime retains the packet's coordinate and rendering behavior;
the first animation callback starts the redraw interval to avoid an immediate second draw.

Actual browser loading also exposed existing boot blockers, repaired here:

- Rename the private bounty-position generator so it does not collide with the exported getter.
- Remove an equivalent duplicate `escapeHtml` declaration in `ui.js`.
- Close `hideAgentSearchResults` before declaring `initCityTeleport`.
- Move the page's existing HTML escaping helper out of JSON-LD metadata into the boot module.

No backend, contract creation, payment, agent registration, or other Track B feature is added.
This is an ordinary source contribution related to
[the Atlas feature issue](https://github.com/Scottcjn/rustchain-bounties/issues/1524).
Earlier minimap PRs [737](https://github.com/Scottcjn/Rustchain/pull/737) and
[746](https://github.com/Scottcjn/Rustchain/pull/746) were closed unmerged; the latter's maintainer
requested focused, one-feature PRs. The earlier source packet's duplicate-claim correction
is preserved: this contribution asserts no new payable bounty claim or payment entitlement.

## Automated checks

```sh
node --test tests/beacon_minimap.test.mjs tests/beacon_boot.test.mjs
python -m pytest --noconftest -q \
  tests/test_beacon_site_ui_frontend_security.py \
  tests/test_beacon_site_agent_panel_xss.py \
  tests/test_beacon_bounty_frontend_security.py \
  tests/test_beacon_atlas.py \
  tests/test_beacon_city_teleport.py \
  tests/test_beacon_agent_leaderboard_ui.py
```

Observed: 6/6 Node tests on Node 24.19.0; 37/37 existing frontend Python tests on
Python 3.12 / pytest 9.1.1 / Node 22.22.0. `--noconftest` runs these frontend checks
without loading the unrelated integrated-node backend fixture. One existing test invokes
`--experimental-default-type=module`, which Node 24.19.0 no longer accepts; that initial
run had 36 passes and one subprocess failure. It passes with the supported Node 22 binary.
The full repository/backend test suite was not run.

## Actual browser run

Install Playwright outside the repository, with a matching browser, then run:

```sh
npm install --prefix /tmp/atlas-browser-test playwright@1.62.1
/tmp/atlas-browser-test/node_modules/.bin/playwright install chromium
NODE_PATH=/tmp/atlas-browser-test/node_modules node tests/beacon_minimap.browser.cjs
```

The runner starts its own local static server and browser in one process, imports the full
Atlas app, and never intercepts requests or substitutes app modules. It records forwarded
Canvas2D calls without changing drawing results, verifies real rendered marker pixels and
canonical positions, operates the real OrbitControls through the minimap rectangle, and
captures the rendered page. It closes both browser and server after the run.

Optional environment settings: `ATLAS_BROWSER_EXECUTABLE` selects an existing matching
Chromium binary; `ATLAS_BROWSER_PROXY` selects a credential-free proxy;
`ATLAS_BROWSER_IGNORE_TLS=1` relaxes browser certificate validation for a local test proxy;
`ATLAS_EVIDENCE_DIR` changes the evidence output directory. Default TLS validation remains on.

Recorded with official Chrome headless shell 151.0.7922.34, Playwright 1.62.1, and SwiftShader
software WebGL. The container required its network proxy and TLS trust relaxation to load
the real CDN modules and public API requests. These results do not validate production TLS
or physical GPU performance. Mobile is Chromium touch emulation at 390×844 with device scale
factor 3; it is not a mobile Safari run. Firefox and Safari were not run.

Both desktop (1280×800) and mobile booted with 117 actual Atlas agents and eight cities.
The receipt records zero JavaScript page errors and zero external write requests,
visible green/amber/cyan marker pixels, matched city/agent drawing counts, camera movement,
responsive canvas dimensions, no gesture interception, and bounded redraw intervals.
The mobile minimap's backing DPR caps at 2.

No local Beacon backend ran on port 8071: relay, contracts, bounties and reputation requests
were unavailable; the app's existing background bounty-sync POST went only to unavailable
localhost. SwarmHub returned 503 / a failed cross-origin request. Real BoTTube and RustChain
public GET data and the app's built-in legacy fallback supplied agents. This run does not
validate backend writes, relay registration, contracts, chat, or provider credentials.

- [Machine-readable browser receipt](browser-receipt.json)
- [Desktop screenshot](desktop.jpg)
- [Mobile screenshot](mobile.jpg)

## AI disclosure

Retained minimap source was prepared by the Z-Sol agent operation named above. This integration,
minimal boot repairs, tests and documentation were completed with OpenAI GPT-6 through Codex
Work Mode (agent collaboration framework). The new patch is predominantly AI-assisted.
The operator authorized this completion and external submission; human diff-level review
is not claimed. The agent read the current upstream, earlier source and duplicate correction,
contribution/onboarding policies, related PR closures, and actual test/runtime output.
