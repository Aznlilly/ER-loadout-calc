# Elden Ring Loadout Optimizer

A fan-made calculator for Elden Ring. Enter your stats, equip what you already want to keep, and it will fill the remaining armor slots for a goal you pick — most poise, most defense, a resistance, or the lightest set that still hits a target. It also ranks weapons and shields against your stats.

Covers the base game, Shadow of the Erdtree, and the Tarnished Pack / Tarnished Edition extras. That extra gear is normal obtainable equipment if you own the pack, not cut or hidden content.

**Not affiliated with FromSoftware or Bandai Namco.** Elden Ring is their game.

## How to open it

This is a web page, but it needs a tiny local server so the browser can load the item data.

1. Install [Python 3](https://www.python.org/downloads/) if you do not already have it.
2. Double-click `run-local.bat` (Windows) or run `./run-local.sh` (macOS / Linux).
3. Your browser should open [http://localhost:8000/](http://localhost:8000/). Leave the terminal window open while you use it; press Ctrl+C there when you are done.

## What you can do

- Type your eight stats. Level and max equip load update from that, including extra load from talismans like Erdtree's Favor or Great-Jar's Arsenal.
- Click a slot to equip armor, weapons, shields, or talismans. Lock a slot if you do not want the optimizer to change it.
- Set a weight cap with Light / Medium / Heavy (the same roll thresholds as the game) or a custom slider.
- Turn sources and map regions on or off, or exclude individual items, so the optimizer only uses gear you actually have access to.
- Import a character from your Elden Ring save. That only *reads* the file in your browser — it is never uploaded and never written back. On Windows, the saves live under `%APPDATA%\EldenRing`. Paste that into the file picker’s address bar, open your Steam ID folder, and choose `ER0000.sl2` (or `ER0000.co2` for a Seamless Co-op save).

Weapon recommendations use each weapon's scaling against your stats. Turn on affinities to rank Heavy / Keen / Occult / … from the game files; if you imported a save, only infusions you own are used, and upgrade levels come from that save. Attack numbers in the table are still wiki reference values at a high, fixed stat investment, not live Attack Rating for *your* stats and upgrade. Use the ranking as a guide for which weapons your spread actually pays off.

Your stats, equipment, and settings are remembered in this browser. Item-pool excludes last for the session only.

If a number, location, or item looks wrong, [open a GitHub issue](https://github.com/Aznlilly/ER-loadout-calc/issues).

## Where the data comes from

- **Armor weight, absorption, resistances, and poise** come from Elden Ring’s own game data (`EquipParamProtector`).
- **Weapon affinity scaling** (Heavy, Keen, Occult, and the rest) comes from `EquipParamWeapon`. Upgrade level is read from your save when you import one; this build does not compute live Attack Rating at +N (that needs the game’s reinforce graphs).
- **Where to find things** is merged from two places: labeled map/enemy lots and shops in `ItemLotParam` / `ShopLineupParam` (names like `[Stormveil - Godrick]` or `[Merchant - North Limgrave]`), plus the community Elden Ring wiki on Fextralife for unnamed world drops, quest text, and region lists the param labels do not spell out. Param files do not store “Limgrave” as a field — they store lot names, which we map onto the same region chips.
- **Item icons, weapon reference attack, and talisman effect text** still come from that wiki.
- **Save import** matches items using IDs from those same game data tables, including the affinity and upgrade encoded in a weapon ID, so a Heavy Longsword +12 in the save is that same Heavy Longsword +12 here.
