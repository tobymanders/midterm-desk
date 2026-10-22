# The Midterm Desk

## Hosted dashboard

GitHub Pages deployment targets https://tobymanders.github.io/midterm-desk/.
The site is public. A private source repository requires a GitHub plan that supports
Pages for private repositories; otherwise the repository must also be public.

The `Update and publish Midterm Desk` workflow runs on pushes to `main`, manual dispatch,
and every six hours at 00:17, 06:17, 12:17 and 18:17 UTC. It fetches public APIs on the
GitHub runner and publishes only `public/index.html`, `public/snapshot.json` and `.nojekyll`.
No API credentials or always-on computer are needed. Scheduled runs are best-effort.

Published **Reload data** fetches the latest same-site snapshot; it does not make visitors
query the polling or betting APIs. Open pages check for a new snapshot every six hours.
The source panel retains the actual retrieval times and reports stale or failed sources.
A cached previous snapshot provides fallback data between workflow runs.

To deploy manually, open the repository's **Actions** tab, select **Update and publish
Midterm Desk**, and choose **Run workflow**. Configure **Settings → Pages → Source** as
**GitHub Actions**. Changes go live after a successful workflow run.

Build locally without new API requests:

```sh
python3 build_static.py
```

Build with fresh API data:

```sh
python3 build_static.py --refresh
```

The public output is in `public/`, which is ignored by Git. The local server below remains
available for development; it is not part of the hosted deployment.


Open **dashboard.html** in any modern browser. It is a standalone, dependency-free HTML dashboard with a verified data snapshot embedded inside it. No CDN, font download, or server is needed to view or interact with it.

It contains one combined generic-ballot plot (Silver Bulletin and FiftyPlusOne) a Senate-control comparison plot beside the ballot plot, and ten Senate race plots comparing Kalshi and Polymarket Republican win probabilities. Hover, keyboard arrows, legend toggles, range buttons, drag-to-zoom, search, sorting, CSV export, and standalone HTML export are supported.

## Live API refresh

Some publishers do not allow browser cross-origin access. For reliable live refreshes, run:

```sh
cd /Users/tobymanders/Code/poll_avg
python3 server.py
```

Open http://127.0.0.1:8765 and click **Refresh data**. The open dashboard also refreshes every five minutes. Collection can take around 30 seconds. Python 3's standard library is sufficient; no API keys or packages are required. The server binds only to localhost, serves only the dashboard and its two API endpoints, and performs read-only public-data requests.

To update the snapshot and standalone file without running the server:

```sh
python3 data_api.py
```

To share a refreshed dashboard, click **Save current HTML**. The downloaded file embeds the displayed dataset. File-mode direct API refresh is best-effort; use the local server when publishers block it.

## Sources and definitions

- Silver Bulletin: https://static.dwcdn.net/data/rfiFi.csv — the current published Datawrapper dataset, rather than a fixed, older chart revision. Model D/R estimates are displayed as published.
- FiftyPlusOne: https://fiftyplusone.news/polls/generic-ballot/generic-ballot/__data.json — public chart data, decoded from Svelte's indexed JSON. Uses “All polls.” The commercial bulk API requires a subscription; this dashboard does not bypass that access requirement.
- Kalshi: https://api.elections.kalshi.com/trade-api/v2 — 2026 general-election Republican-party YES contracts; latest bid/ask midpoint and daily closing bid/ask midpoints.
- Polymarket: https://gamma-api.polymarket.com — current Republican-party YES outcome prices; https://clob.polymarket.com/prices-history for daily historical samples.

The Senate universe includes the 33 regularly scheduled seats plus the Florida and Ohio special elections. A race must have a usable quote on both exchanges. Closeness is the average of each exchange's absolute distance from 50%. The ten smallest distances are selected **before** search or sorting. This avoids treating a 10%/90% exchange disagreement as a 50–50 race. Independent candidates are not silently classified as Democrats. Alaska is labeled explicitly: Kalshi quotes the Republican party, while Polymarket’s Democratic probability uses Mary Peltola’s YES contract directly. These are different events, so the small exchange gap there is not a pure price comparison. The official Alaska candidate list is linked in the dashboard. Alaska’s candidate YES probability and history are normalized to the opposite-side representation internally, then converted back to the quoted Democratic side for display; this prevents labeling a Sullivan YES price as Democratic.

Market prices measure implied probability of winning, not vote share. Markets differ in liquidity, pricing convention and settlement rules; inspect the linked contracts. Daily samples are not synchronized intraday trades. Gaps are not invented. Timestamps are retrieval times, not proof of a recent trade.

Missing quotes and failed requests are reported; stale saved data is retained and labeled after failures. Current-source and universe coverage are shown in the source panel. Refresh writes `snapshot.json` and `dashboard.html`; `dashboard.template.html` is the editable layout, and `data_api.py` contains the source adapters.

## Verification

Verified with live API responses and headless Chrome at desktop and mobile widths: 12 plots, range and measure controls, race search, legend toggles, hover values, modal controls, and portable HTML export. No JavaScript errors or horizontal mobile overflow.

Senate charts and readouts use the leading side’s full win probability: D65% means a 65% Democratic win probability; R54% means a 54% Republican win probability. Ties read 50–50. Democratic values and plot segments are blue; Republican values and segments are red. Exchanges are distinguished by solid (Kalshi) and dashed (Polymarket) lines. Nebraska uses I if the independent side leads. Raw probabilities remain in the data and CSV export.

Both ballot publishers share one plot: party is encoded by blue/red, publisher by solid/dashed lines. Vote-share view has four series; margin view has two. Each series can be toggled independently.

Senate control uses Kalshi CONTROLS-2026-R and Polymarket’s Republican Party YES contract in “Which party will win the Senate in 2026?”. These are direct chamber-control markets, not estimates derived from the ten displayed races. Both have independent 7/30/90-day history controls, live refresh, source links, and CSV export.
