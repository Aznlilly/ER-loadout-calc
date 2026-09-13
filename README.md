# Elden Ring Loadout Optimizer

A static, client-side (vanilla JS, no build step, no backend) tool that optimizes
Elden Ring armor loadouts for your character's stats and a chosen goal — and
gives weapon recommendations based on your stat spread. Designed to be hosted
for free on GitHub Pages.

**Not affiliated with FromSoftware or Bandai Namco.** Item data was sourced
from the Elden Ring wiki on Fextralife (community-maintained reference data),
covering the base game, the Shadow of the Erdtree DLC, and the "Tarnished
Edition" bonus content — the extra armor added by the Nintendo Switch 2
"Elden Ring Tarnished Edition" release / the cross-platform "Tarnished Pack"
DLC (released August 28, 2026 via Patch 1.17). That content is normal,
obtainable equipment for anyone who owns the pack — found from merchants,
world pickups, and a boss drop, just like any other item — not unobtainable
or special/hidden content.

## Features

- Enter your 8 base stats; the tool derives your character level and max
  equip load (including any equip-load-boosting talismans, e.g. Great-Jar's
  Arsenal or Erdtree's Favor — detected automatically from talisman effect
  text, not hardcoded).
- Pick up to 4 talismans (weight and equip-load/poise bonuses are factored in).
- Equip weapons and shields in either hand; their weight is subtracted from
  the armor optimizer's load budget.
- Optimize your 4 armor slots (helm/chest/gauntlets/legs) for one of:
  - **Max Poise** within a weight budget
  - **Max Total Damage Negation** within a weight budget
  - **Max a specific resistance** (Immunity / Robustness / Focus / Vitality)
    within a weight budget
  - **Min weight** needed to hit a target Poise or Negation value
- Weight budget can be set via Light/Medium/Heavy presets (matching the
  game's roll-speed thresholds: <30% / <70% / <100%) or a custom slider.
- **Item Pool panel**: every armor piece, weapon, shield, and talisman is tagged with
  its `source` — `"Elden Ring"` (base game), `"Shadow of the Erdtree"` (DLC),
  or `"Tarnished Edition"` (Tarnished Pack DLC, released Aug 2026) — all
  three are shown and enabled by default, since all three are normal,
  obtainable content for anyone who owns the relevant game/DLC. Toggle whole
  sources on/off with the checkboxes, or click "Customize Item
  Pool" to open a slide-out drawer with per-tab (Armor/Weapons/Talismans)
  checklists — search, uncheck individual items to exclude them from the
  optimizer and weapon rankings, and use the **All** / **None** / **Reset
  All Excludes** buttons to bulk-manage your pool. Excludes persist across
  tabs and re-optimizations for the rest of your session.
- **Filter by location**: chips are an access filter, not bulk checkboxes.
  An item is in the pool if **any** of its obtain paths is turned on (so
  Champion Headband is available from Starting Gear *or* Caelid, not both).
  **None**, then **Limgrave**, for a Limgrave-only run. **Starting Gear**
  (first chip) is every class kit — leave it off, or turn it on and uncheck
  classes you did not pick in Customize. Untagged items are included only
  when every chip is on (**All**). Customize still excludes individual
  pieces without turning a region chip off.
- Toggle "Altered" armor variants on/off.
- Weapon recommendations ranked by how well your stats pay off each weapon's
  scaling grades, filtered by whether you meet its Str/Dex/Int/Fai/Arc
  requirements (with two-handing's 1.5× Strength bonus accounted for), and
  by your current Item Pool source/exclude settings.

## How the optimizer works

Picking the best armor for each of the 4 slots under a shared weight budget
is a **Multiple-Choice Knapsack Problem**: choose exactly one item per slot to
maximize (or, in "min weight" mode, satisfy a target while minimizing) a
value, subject to a total weight cap. `js/optimizer.js` solves this exactly
with a weight-discretized dynamic program (0.1-unit resolution) — this is not
a greedy or heuristic approximation, it finds the true optimum over the full
item pool (roughly 200 items per slot) in well under a second.

## Weapon AR caveat

FromSoftware hasn't published the exact per-weapon scaling-curve formulas
used to compute Attack Rating at arbitrary stat values, so this tool does
**not** invent a fabricated AR number for your exact stats. Instead it shows
a wiki reference AR (at a fixed, high stat investment) alongside a
stat-weighted "scaling payoff" ranking, and is upfront in the UI that the AR
column is a reference value, not computed from your exact build.

## Project structure

```
index.html              Main page
css/style.css            Styling
js/calc.js                Equip load / poise / negation math
js/optimizer.js           The knapsack-DP armor optimizer
js/weapons.js              Weapon filtering & ranking
js/app.js                  UI wiring
data/armor.json             727 armor pieces (566 Elden Ring / 145 Shadow of the Erdtree / 16 Tarnished Edition), each tagged with "source"
data/weapons.json            Weapons and shields (378 Elden Ring / 101 Shadow of the Erdtree / 8 Tarnished Edition), each tagged with "source"
data/talismans.json           155 talismans (116 Elden Ring / 39 Shadow of the Erdtree), each tagged with "source"
data/equip_load_table.json     Endurance -> max equip load lookup table
data/raw/region_items.json     Per-region "found in this zone" item-name lists scraped from the wiki, used to derive "areas"
data/raw/                    Intermediate scraped JSON (not served; wiki HTML cache is gitignored)
scripts/build_*.py            Rebuild data/*.json from data/raw/*.json
.github/workflows/pages.yml    Publishes the static site to GitHub Pages
scripts/test_optimizer.js      Node sanity tests for the optimizer against real data
scripts/e2e_test.py            Playwright end-to-end test of the live page
```

## Running locally

No build step needed — it's plain HTML/CSS/JS fetching local JSON files.
Because browsers block `fetch()` of local files over `file://`, it needs to
be served by a local web server. Easiest way: double-click (Windows) or run
one of the included scripts, which start a server and open the page for you:

```
run-local.bat      # Windows: double-click it, or run from a terminal
./run-local.sh      # macOS / Linux
```

Requires Python 3 to be installed (both scripts use `python -m http.server`
under the hood). By default it serves on port 8000
(`http://localhost:8000/`); pass a different port to `run-local.sh` if 8000
is taken (`./run-local.sh 8080`), or edit the `PORT` line in `run-local.bat`.
Stop the server with Ctrl+C in that window.

Prefer to do it by hand? Any static file server works, e.g.:

```
python3 -m http.server 8000
```

Then open `http://localhost:8000/`.

## Deploying to GitHub Pages

The live site is only `index.html`, `css/`, `js/`, `img/`, and `data/*.json`.
A GitHub Actions workflow (`.github/workflows/pages.yml`) publishes those
files on every push to `main`. Rebuild scripts and `data/raw/` stay in git
but are not uploaded.

### 1. Create the GitHub repo

On [github.com/new](https://github.com/new): name it (e.g. `ER-loadout-calc`),
leave it **empty** (no README / gitignore / license), and create it. Public
repos get free GitHub Pages.

Or from this folder, after you have [GitHub CLI](https://cli.github.com/)
logged in (`gh auth login`):

```
gh repo create ER-loadout-calc --public --source=. --remote=origin
```

### 2. First commit and push

This folder is not a git repo yet. In a terminal here:

```
git init
git add .
git commit -m "Initial commit: Elden Ring loadout optimizer"
git branch -M main
git remote add origin https://github.com/<your-username>/ER-loadout-calc.git
git push -u origin main
```

Skip `git remote add` if you used `gh repo create --remote=origin` above;
then just `git branch -M main` and `git push -u origin main`.

### 3. Turn on Pages

1. Open the repo on GitHub → **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Open the **Actions** tab, wait for **Deploy GitHub Pages** to finish
   (first run can take a couple of minutes because of the item images).

The site URL is:

`https://<your-username>.github.io/ER-loadout-calc/`

If the repo is named `<your-username>.github.io`, it will be
`https://<your-username>.github.io/` instead.

All `fetch()` paths in the app are relative, so a project site
(`…/ER-loadout-calc/`) works with no extra config. The empty `.nojekyll`
file tells Pages not to run Jekyll on the uploaded files.

### Later updates

```
git add -A
git commit -m "Describe the change"
git push
```

GitHub Actions deploys again automatically. Hard-refresh the live page if
you still see an old build.

## Regenerating the data

If you want to refresh the item data (e.g. after a game balance patch), the
`scripts/build_*.py` scripts rebuild `data/*.json` from the intermediate
files in `data/raw/*.json`. Those raw files were captured from the Fextralife
wiki's comparison tables; see the scripts for the exact field mapping. Wiki
HTML caches under `data/raw/wiki_cache/` are local-only and gitignored.

## Known gaps / possible follow-ups

- Area tags (`"areas"` field) are independent obtain paths, not a single
  map pin. Location chips are an access filter: an item is in the pool if
  **any** of its places is turned on. Unique/quest/shop pickups use armor
  `acquire` / talisman `location` prose. Generic world drops also use the
  wiki's per-region item lists. Weapons still rely mainly on those lists
  (the raw weapon tables have no location field); the eight Tarnished Pack
  weapons are tagged from their item-page locations instead. Class kits
  also have a **Starting Gear** chip (before Limgrave). Altered and
  unaltered armor are tagged separately when their drop spots differ
  (Stormveil Banished Knights drop the altered chest/helm, not the cape
  versions). Each item also has a `"wiki"` URL. Untagged items are only
  included when every location chip is on (All). Ammo, spells and
  consumables mentioned in the region lists are intentionally not matched
  since they aren't part of this tool's datasets.
- No talismans are tagged as "Tarnished Edition" yet. The eight Tarnished
  Pack weapons are scraped from wiki item infoboxes because the global
  comparison tables still omit them.
- No talisman auto-selection — the optimizer treats your 4 chosen talismans
  as fixed and only searches over armor. Auto-picking talismans too would
  turn this into a larger combinatorial search (talisman effects are too
  varied to score generically without more design work).
