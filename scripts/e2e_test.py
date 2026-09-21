import sys
from playwright.sync_api import sync_playwright

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium/chrome-linux/chrome" if False else None)
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))

    page.goto("http://localhost:8000/index.html", wait_until="networkidle")
    page.wait_for_timeout(500)
    page.evaluate("() => localStorage.clear()")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(400)

    # Sanity: derived level shown
    level = page.text_content("#derived-level")
    print("Derived level:", level)
    if level.strip() != "1":
        raise SystemExit("default stats of 10 should be character level 1")

    footer_html = page.inner_html(".site-footer")
    print("Issues footer present:", "github.com/Aznlilly/ER-loadout-calc/issues" in footer_html)
    if "github.com/Aznlilly/ER-loadout-calc/issues" not in footer_html:
        raise SystemExit("footer should link to the GitHub issues page")

    load_save = page.locator("#load-save-btn")
    print("Load Save button:", load_save.count())
    if load_save.count() != 1:
        raise SystemExit("Load Save should be in its own section near the top")
    section_order = page.evaluate("""() => Array.from(document.querySelectorAll("main > section.panel")).map(s => s.id)""")
    print("Section order:", section_order)
    expected = ["panel-save", "panel-character", "panel-equipment", "panel-status", "panel-item-pool", "panel-goal", "panel-results", "panel-weapons"]
    if section_order != expected:
        raise SystemExit(f"unexpected section order: {section_order}")
    if page.locator("#panel-save #load-save-btn").count() != 1:
        raise SystemExit("Load Save button should live in the top Load Save section")
    if page.locator("#panel-item-pool #load-save-btn").count() != 0:
        raise SystemExit("Load Save should not still be inside Item Pool")
    hint = page.inner_text(".save-import-hint")
    if "ER0000.sl2" not in hint or "ER0000.co2" not in hint:
        raise SystemExit("save import hint should mention .sl2 and Seamless .co2")
    if "paste" not in hint.lower() or "Steam ID" not in hint or "%APPDATA%\\EldenRing" not in hint:
        raise SystemExit("save import hint should tell you to paste %APPDATA%\\EldenRing and open your Steam ID folder")
    if page.locator("#copy-save-path-btn").count() != 1:
        raise SystemExit("save import hint should have a Copy button for the path")
    safe = page.inner_text(".save-import-safe")
    if "does not modify your save" not in safe.lower() or "only reads" not in safe.lower():
        raise SystemExit("save import should warn in red that the save file is read-only")
    overlay_hidden = page.evaluate("() => document.getElementById('save-character-overlay').classList.contains('hidden')")
    if not overlay_hidden:
        raise SystemExit("character picker should start hidden")
    for cid in ("save-import-inventory", "save-import-chest", "save-import-stats", "save-import-equipped", "save-import-confirm"):
        if page.locator(f"#{cid}").count() != 1:
            raise SystemExit(f"save import dialog should include {cid}")
    ids_ok = page.evaluate("() => GAME_IDS && GAME_IDS.weapons && GAME_IDS.weapons['2000000'] === 'longsword'")
    print("Game ID table loaded:", ids_ok)
    if not ids_ok:
        raise SystemExit("game_ids.json should map Longsword")
    runes_ok = page.evaluate(
        """() => GREAT_RUNES && GREAT_RUNES.length === 6 && GREAT_RUNES_BY_ID.get("godrick-s-great-rune")"""
    )
    print("Great Runes loaded:", bool(runes_ok))
    if not runes_ok:
        raise SystemExit("great-runes.json should load six Great Runes including Godrick's")
    if page.locator('[data-slot="rune"]').count() != 1:
        raise SystemExit("equipment board should have a Great Rune slot")
    bonus_ok = page.evaluate(
        """() => {
      const expected = {
        "radagon-s-scarseal": { vig: 3, end: 3, str: 3, dex: 3 },
        "radagon-s-soreseal": { vig: 5, end: 5, str: 5, dex: 5 },
        "marika-s-scarseal": { mind: 3, int: 3, fai: 3, arc: 3 },
        "marika-s-soreseal": { mind: 5, int: 5, fai: 5, arc: 5 },
        "starscourge-heirloom": { str: 5 },
        "prosthesis-wearer-heirloom": { dex: 5 },
        "stargazer-heirloom": { int: 5 },
        "two-fingers-heirloom": { fai: 5 },
        "outer-god-heirloom": { arc: 5 },
        "millicent-s-prosthesis": { dex: 5 },
      };
      const keys = ["vig", "mind", "end", "str", "dex", "int", "fai", "arc"];
      for (const t of TALISMANS) {
        const got = parseAttributeBonuses(t.effect);
        const want = expected[t.id] || {};
        for (const k of keys) {
          if ((got[k] || 0) !== (want[k] || 0)) return `${t.id} ${k}=${got[k]}`;
        }
      }
      const stacked = applyEffectiveStats(
        { vig: 10, mind: 10, end: 10, str: 10, dex: 10, int: 10, fai: 10, arc: 10 },
        [TALISMANS.find((t) => t.id === "radagon-s-soreseal")],
        GREAT_RUNES_BY_ID.get("godrick-s-great-rune"),
        true
      );
      if (stacked.end !== 20 || stacked.mind !== 15) return "stack";
      const armorWant = {
        "chest-commoner-s-garb": { fai: 1 },
        "helm-high-priest-hat": { int: 1, arc: 1 },
        "helm-thiollier-s-mask": { arc: 3 },
        "chest-gold-tattoo-chest": { fai: 2 },
        "helm-haligtree-knight-helm": { fai: 2 },
        "helm-salza-s-hood": { int: 2 },
      };
      for (const [id, want] of Object.entries(armorWant)) {
        const item = ARMOR.find((a) => a.id === id);
        if (!item) return `missing ${id}`;
        const got = itemAttributeBonuses([item]);
        for (const k of keys) {
          if ((got[k] || 0) !== (want[k] || 0)) return `${id} ${k}=${got[k]}`;
        }
      }
      return "ok";
    }"""
    )
    print("Attribute bonus parser:", bonus_ok)
    if bonus_ok != "ok":
        raise SystemExit(f"talisman/rune attribute bonuses failed: {bonus_ok}")
    variants_ok = page.evaluate(
        """() => WEAPON_VARIANTS && WEAPON_VARIANTS.longsword && WEAPON_VARIANTS.longsword['100']"""
    )
    print("Weapon variants loaded:", bool(variants_ok))
    if not variants_ok:
        raise SystemExit("weapon_variants.json should include Heavy Longsword")
    for cid, label in (
        ("include-affinities", "weapon affinities"),
        ("include-upgrades", "weapon upgrade levels"),
    ):
        el = page.locator(f"#{cid}")
        if el.count() != 1:
            raise SystemExit(f"item pool should have a {label} checkbox")
        if not page.evaluate(f"() => document.getElementById('{cid}').checked"):
            raise SystemExit(f"{cid} should be on by default")
    maus_w = page.evaluate(
        """() => {
      const un = ARMOR.find(a => a.name === "Mausoleum Knight Armor");
      const al = ARMOR.find(a => a.name === "Mausoleum Knight Armor (Altered)");
      return { un: un && un.weight, al: al && al.weight };
    }"""
    )
    print("Mausoleum Knight Armor weights:", maus_w)
    if maus_w["un"] != 11.8:
        raise SystemExit("Mausoleum Knight Armor should weigh 11.8")
    if maus_w["al"] != 10.8:
        raise SystemExit("Mausoleum Knight Armor (Altered) should weigh 10.8")

    foot_g = page.evaluate(
        """() => {
      const g = ARMOR.find(a => a.name === "Foot Soldier Greaves");
      return g && { weight: g.weight, poise: g.resistance && g.resistance.poise, areas: g.areas, slot: g.slot };
    }"""
    )
    print("Foot Soldier Greaves:", foot_g)
    if not foot_g:
        raise SystemExit("Foot Soldier Greaves should be in the armor pool")
    if foot_g["slot"] != "legs" or foot_g["weight"] != 5.1:
        raise SystemExit("Foot Soldier Greaves should be 5.1 weight legs")
    if foot_g["poise"] != 10:
        raise SystemExit("Foot Soldier Greaves poise should be 10")
    if "Limgrave" not in foot_g["areas"]:
        raise SystemExit("Foot Soldier Greaves should drop in Limgrave")

    exclusive_start = page.evaluate(
        """() => {
      const out = [];
      for (const it of [...ARMOR, ...WEAPONS]) {
        if (!(it.startingClasses && it.startingClasses.length)) continue;
        const world = (it.areas || []).filter(a => a !== "Starting Gear");
        if (!world.length) out.push(it.name);
      }
      return out;
    }"""
    )
    print("Starting gear missing a world location:", exclusive_start)
    if exclusive_start:
        raise SystemExit(f"starting gear should also have a world location: {exclusive_start}")

    page.fill("#stat-str", "25")
    page.wait_for_timeout(150)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(400)
    saved_str = page.input_value("#stat-str")
    print("Strength after reload:", saved_str)
    if saved_str != "25":
        raise SystemExit("stats should persist across reloads")
    page.fill("#stat-str", "10")
    page.wait_for_timeout(100)

    page.click('[data-slot="rune"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "godrick")
    page.wait_for_timeout(200)
    page.click("#picker-list .pick-item")
    page.wait_for_timeout(200)
    rune_name = page.text_content('[data-slot="rune"] .slot-name')
    print("Equipped Great Rune:", rune_name)
    if "Godrick" not in (rune_name or ""):
        raise SystemExit("should be able to equip Godrick's Great Rune")
    load_off = float(page.text_content("#derived-base-load"))
    page.click("[data-rune-active]")
    page.wait_for_timeout(200)
    load_on = float(page.text_content("#derived-base-load"))
    end_txt = page.inner_text("#status-attr-end")
    hp_on = page.inner_text("#status-hp")
    pressed = page.get_attribute("[data-rune-active]", "aria-pressed")
    print("Load with Godrick off/on:", load_off, load_on, "pressed", pressed, "END", end_txt)
    if pressed != "true":
        raise SystemExit("Rune Arc toggle should become active")
    if load_on <= load_off:
        raise SystemExit("active Godrick's Great Rune should raise endurance-based max load")
    if "15" not in end_txt:
        raise SystemExit("active Godrick's should show effective endurance 15")
    end_html = page.inner_html("#status-attr-end")
    if "Godrick" not in end_html:
        raise SystemExit("endurance tooltip should list Godrick's Great Rune")
    if "→" not in hp_on:
        raise SystemExit("active Godrick's should raise HP above the invested-vigor base")
    page.click('[data-slot="chest"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "Commoner's Simple Garb")
    page.wait_for_timeout(200)
    page.click('#picker-list [data-item-id="chest-commoner-s-simple-garb"]')
    page.wait_for_timeout(200)
    page.click('[data-slot="tal1"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "Two Fingers Heirloom")
    page.wait_for_timeout(200)
    page.click('#picker-list [data-item-id="two-fingers-heirloom"]')
    page.wait_for_timeout(200)
    fai_html = page.inner_html("#status-attr-fai")
    print("Faith tooltip:", fai_html)
    if "Godrick" not in fai_html or "Commoner" not in fai_html or "Two Fingers" not in fai_html:
        raise SystemExit("faith tooltip should list Godrick's Great Rune, Commoner's Simple Garb, and Two Fingers Heirloom")
    if "+5" not in fai_html or "+1" not in fai_html:
        raise SystemExit("faith tooltip should include each contributor's amount")
    page.evaluate(
        """() => {
      setSlotItem("chest", null);
      setSlotItem("tal1", null);
    }"""
    )
    rune_import = page.evaluate(
        """() => {
      applySaveCharacter({
        name: "RuneImporter",
        level: 12,
        stats: { greatRuneOn: true },
        equipped: { rune: { type: "greatRunes", id: 191 } },
      }, { equipped: true });
      return { id: greatRuneId, active: greatRuneActive };
    }"""
    )
    print("Imported Great Rune:", rune_import)
    if rune_import["id"] != "godrick-s-great-rune" or not rune_import["active"]:
        raise SystemExit("equipped import should set Godrick's Great Rune and Rune Arc active")
    page.evaluate(
        """() => {
      greatRuneId = null;
      greatRuneActive = false;
      saveState();
      renderEquipment();
      updateDerivedCharacterInfo();
    }"""
    )

    load_plain = float(page.text_content("#derived-base-load"))
    soreseal_load = page.evaluate(
        """() => {
      setSlotItem("tal1", "radagon-s-soreseal");
      return document.getElementById("derived-base-load").textContent;
    }"""
    )
    soreseal_end = page.inner_text("#status-attr-end")
    soreseal_mind = page.inner_text("#status-attr-mind")
    print("Load with Radagon's Soreseal:", load_plain, soreseal_load)
    if float(soreseal_load) <= load_plain:
        raise SystemExit("Radagon's Soreseal should raise endurance-based max load")
    if "15" not in soreseal_end:
        raise SystemExit("Radagon's Soreseal should show effective endurance 15")
    if "→" in soreseal_mind:
        raise SystemExit("Radagon's Soreseal should not boost mind")
    wield = page.evaluate(
        """() => {
      const mace = WEAPONS.find((w) => w.id === "mace");
      const before = checkRequirements(mace, getStats(), false);
      setSlotItem("tal1", "starscourge-heirloom");
      const after = checkRequirements(mace, getEffectiveStats(), false);
      const str = getEffectiveStats().str;
      setSlotItem("tal1", null);
      return { beforeMet: before.met, afterMet: after.met, str };
    }"""
    )
    print("Mace wield with Starscourge Heirloom:", wield)
    if wield["beforeMet"] or not wield["afterMet"] or wield["str"] != 15:
        raise SystemExit("Starscourge Heirloom should let STR 10 meet Mace's 12 STR")
    page.evaluate("() => { setSlotItem('tal1', null); }")

    heavy_rank = page.evaluate(
        """() => {
      const stats = { str: 80, dex: 12, int: 9, fai: 9, arc: 7 };
      const ls = WEAPONS.filter(w => w.id === "longsword");
      const ranked = rankWeapons(ls, stats, {
        onlyMeetable: true,
        includeAffinities: true,
        variants: WEAPON_VARIANTS,
      });
      const heavy = ranked.find(r => r.affinity === 100);
      const keen = ranked.find(r => r.affinity === 200);
      return {
        heavy: heavy && heavy.payoff,
        keen: keen && keen.payoff,
        labels: ranked.slice(0, 3).map(r => r.label),
      };
    }"""
    )
    print("Longsword infusion payoffs at 80 STR:", heavy_rank)
    if not heavy_rank or heavy_rank["heavy"] is None or heavy_rank["keen"] is None:
        raise SystemExit("should rank Heavy and Keen Longsword when affinities are on")
    if not (heavy_rank["heavy"] > heavy_rank["keen"]):
        raise SystemExit("80 STR should prefer Heavy Longsword over Keen")

    # Talisman pouches: 2 active slots
    page.select_option("#talisman-slot-count", "2")
    page.wait_for_timeout(200)
    tal3_class = page.get_attribute('[data-slot="tal3"]', "class")
    tal4_class = page.get_attribute('[data-slot="tal4"]', "class")
    print("Talisman 3 inactive at pouch count 2:", "inactive" in (tal3_class or ""))
    print("Talisman 4 inactive at pouch count 2:", "inactive" in (tal4_class or ""))
    if "inactive" not in (tal3_class or "") or "inactive" not in (tal4_class or ""):
        raise SystemExit("expected tal3/tal4 inactive when pouches=2")

    # Equip + lock a helm
    page.click('[data-slot="helm"]')
    page.wait_for_timeout(200)
    page.click("#picker-list .pick-item")
    page.wait_for_timeout(200)
    helm_before = page.text_content('[data-slot="helm"] .slot-name')
    print("Equipped helm:", helm_before)
    page.click('[data-lock="helm"]')
    page.wait_for_timeout(150)
    helm_locked_class = page.get_attribute('[data-slot="helm"]', "class")
    print("Helm locked:", "locked" in (helm_locked_class or ""))

    # Equip + lock a weapon in R1
    page.click('[data-slot="r1"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "dagger")
    page.wait_for_timeout(200)
    page.locator("#picker-list .pick-item").first.click()
    page.wait_for_timeout(200)
    r1_before = page.text_content('[data-slot="r1"] .slot-name')
    print("Equipped R1:", r1_before)
    page.click('[data-lock="r1"]')
    page.wait_for_timeout(150)

    page.click('[data-slot="l1"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "Beast Crest Heater Shield")
    page.wait_for_timeout(200)
    page.locator("#picker-list .pick-item").first.click()
    page.wait_for_timeout(200)
    l1_name = page.text_content('[data-slot="l1"] .slot-name')
    print("Equipped L1:", l1_name)
    if "Beast Crest Heater" not in (l1_name or ""):
        raise SystemExit("expected Beast Crest Heater Shield in L1")
    page.click('[data-slot="r2"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "Beast Crest Heater Shield")
    page.wait_for_timeout(200)
    r2_picker = page.inner_html("#picker-list")
    print("Shields also in right-hand picker:", "Beast Crest Heater" in r2_picker)
    page.click("#picker-close")

    # Equip + lock a talisman in slot 1
    page.click('[data-slot="tal1"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "great-jar")
    page.wait_for_timeout(200)
    page.click("#picker-list .pick-item")
    page.wait_for_timeout(200)
    tal1_name = page.text_content('[data-slot="tal1"] .slot-name')
    print("Equipped talisman 1:", tal1_name)

    # Set endurance and check budget updates
    page.fill("#stat-end", "60")
    page.wait_for_timeout(200)
    maxload = page.text_content("#derived-maxload")
    print("Max load after END=60 + equipped talisman:", maxload)
    budget_text = page.text_content("#derived-budget")
    print("Armor budget line:", budget_text)
    if "shield" not in (budget_text or "").lower():
        raise SystemExit("armor budget should subtract equipped shield weight")

    # Light / Medium / Heavy presets must stick at 29.9 / 69.9 / 99.9
    for preset, expected, slider in [
        ("0.299", 0.299, "299"),
        ("0.699", 0.699, "699"),
        ("0.999", 0.999, "999"),
    ]:
        page.click(f'.preset-btn[data-preset="{preset}"]')
        got_slider = page.input_value("#load-ratio")
        got_ratio = page.evaluate("() => getLoadBudget().ratio")
        label = page.text_content("#load-ratio-value")
        print(f"Preset {preset}: slider={got_slider} ratio={got_ratio} label={label}")
        if got_slider.strip() != slider:
            raise SystemExit(f"preset {preset} slider should be {slider}, got {got_slider}")
        if abs(float(got_ratio) - expected) > 0.0005:
            raise SystemExit(f"preset {preset} should use ratio {expected}, got {got_ratio}")
        expected_label = f"{expected * 100:.1f}%"
        if label.strip() != expected_label:
            raise SystemExit(f"preset {preset} label should be {expected_label}, got {label}")

    # Click Medium preset then optimize
    page.click('.preset-btn[data-preset="0.699"]')
    page.click("#optimize-btn")
    page.wait_for_timeout(500)
    results_html = page.inner_html("#results-content")
    print("Results panel has table:", "<table" in results_html)
    helm_after = page.text_content('[data-slot="helm"] .slot-name')
    r1_after = page.text_content('[data-slot="r1"] .slot-name')
    print("Helm after optimize (should match):", helm_after)
    print("R1 after optimize (should match):", r1_after)
    if helm_after.strip() != helm_before.strip():
        raise SystemExit("locked helm changed after optimize")
    if r1_after.strip() != r1_before.strip():
        raise SystemExit("locked weapon changed after optimize")
    chest_name = page.text_content('[data-slot="chest"] .slot-name')
    print("Chest filled:", chest_name)
    if chest_name.strip() in ("Empty", "", None):
        raise SystemExit("unlocked chest was not filled")
    load_badge = page.locator("#results-content .badge").first.text_content()
    print("Load badge after Medium optimize:", load_badge)
    if "heavy" in (load_badge or "").lower() or "overload" in (load_badge or "").lower():
        raise SystemExit(f"Medium (<70%) optimize should stay under heavy, got {load_badge}")

    cap_checks = page.evaluate(
        """() => {
          const out = {};
          for (const ratio of [0.299, 0.45, 0.699, 0.70, 0.999, 1.0]) {
            applyLoadRatio(ratio);
            const b = getLoadBudget();
            const result = optimizeArmor(getArmorPool(), { type: "poise" }, b.budgetForArmor, getRequiredArmorSlots());
            let armorW = 0;
            if (result && result.selection) {
              for (const s of ARMOR_SLOTS) {
                const it = result.selection[s];
                if (it && it.weight) armorW += it.weight;
              }
            }
            const total = result ? armorW + b.talismanWeight + b.weaponWeight : null;
            const got = total == null || !b.maxLoad ? null : total / b.maxLoad;
            const cls = got == null ? "none" : loadClass(got);
            out[String(ratio)] = {
              used: b.ratio,
              over: total == null ? false : total > b.maxLoad * ratio + 1e-9,
              cls,
              allowed: allowedLoadClass(ratio),
              heavier: got == null ? false : isHeavierLoadClass(cls, allowedLoadClass(ratio)),
              infeasible: !result
            };
          }
          applyLoadRatio(0.699);
          updateLoadBudgetDisplay();
          return out;
        }"""
    )
    print("Load cap checks:", cap_checks)
    for ratio, row in cap_checks.items():
        if abs(float(row["used"]) - float(ratio)) > 0.0005:
            raise SystemExit(f"slider ratio {ratio} stored as {row['used']}")
        if row.get("over"):
            raise SystemExit(f"ratio {ratio} combo exceeded the slider cap")
        if row.get("heavier"):
            raise SystemExit(
                f"ratio {ratio} produced {row.get('cls')} heavier than {row.get('allowed')}"
            )

    sug = page.inner_html("#optimizer-suggestions") if page.locator("#optimizer-suggestions").count() else ""
    print("Suggestions present:", bool(sug))
    print("Suggestions mention tal3:", "tal3" in sug)
    if "data-apply-slot=\"tal3\"" in sug or "data-apply-slot=\"tal4\"" in sug:
        raise SystemExit("suggestions targeted inactive talisman slots")

    print(page.text_content("#results-content")[:600])

    # Try negation goal
    page.check('input[name="goal"][value="negation"]')
    page.click("#optimize-btn")
    page.wait_for_timeout(300)
    print("\n--- negation goal ---")
    print(page.text_content("#results-content")[:400])

    # Try resistance goal
    page.check('input[name="goal"][value="resistance"]')
    page.select_option("#resistance-stat", "robustness")
    page.click("#optimize-btn")
    page.wait_for_timeout(300)
    print("\n--- resistance goal ---")
    print(page.text_content("#results-content")[:400])

    # Try min-weight goal
    page.check('input[name="goal"][value="minweight"]')
    page.fill("#minweight-target", "60")
    page.click("#optimize-btn")
    page.wait_for_timeout(300)
    print("\n--- minweight goal ---")
    print(page.text_content("#results-content")[:400])

    # Weapon panel
    print("\n--- weapons ---")
    print(page.text_content("#weapon-results")[:500])

    page.click("#unequip-all")
    page.wait_for_timeout(200)
    helm_cleared = page.text_content('[data-slot="helm"] .slot-name')
    r1_cleared = page.text_content('[data-slot="r1"] .slot-name')
    l1_cleared = page.text_content('[data-slot="l1"] .slot-name')
    helm_still_locked = "locked" in (page.get_attribute('[data-slot="helm"]', "class") or "")
    print("Unequip All helm (locked, should keep):", helm_cleared)
    print("Unequip All R1 (locked, should keep):", r1_cleared)
    print("Unequip All L1 (unlocked, should clear):", l1_cleared)
    if helm_cleared.strip() != helm_before.strip() or not helm_still_locked:
        raise SystemExit("Unequip All should leave locked helm equipped")
    if r1_cleared.strip() != r1_before.strip():
        raise SystemExit("Unequip All should leave locked R1 equipped")
    if l1_cleared.strip() != "Empty":
        raise SystemExit("Unequip All should empty unlocked slots")

    equipped_import = page.evaluate(
        """() => {
      const helmBefore = EQUIPMENT.helm.id;
      const r1Before = EQUIPMENT.r1.id;
      applySaveCharacter({
        name: "Importer",
        level: 12,
        equipped: {
          helm: { type: "armor", id: 40000 },
          chest: { type: "armor", id: 380100 },
          r1: { type: "weapons", id: 2000000 },
          l1: { type: "weapons", id: 2000110 },
          tal1: { type: "talismans", id: 1000 },
        },
      }, { equipped: true });
      const out = {
        helm: EQUIPMENT.helm.id,
        helmBefore,
        helmLocked: EQUIPMENT.helm.locked,
        r1: EQUIPMENT.r1.id,
        r1Before,
        chest: EQUIPMENT.chest.id,
        l1: EQUIPMENT.l1.id,
        l1Affinity: EQUIPMENT.l1.affinity,
        l1Upgrade: EQUIPMENT.l1.upgrade,
        tal1: EQUIPMENT.tal1.id,
      };
      for (const slot of ALL_SLOTS) {
        if (!EQUIPMENT[slot].locked) EQUIPMENT[slot].id = null;
      }
      saveState();
      renderEquipment();
      updateDerivedCharacterInfo();
      return out;
    }"""
    )
    print("Equipped import:", equipped_import)
    if not equipped_import["helmLocked"] or equipped_import["helm"] != equipped_import["helmBefore"]:
        raise SystemExit("equipped import should leave locked helm unchanged")
    if equipped_import["r1"] != equipped_import["r1Before"]:
        raise SystemExit("equipped import should leave locked R1 unchanged")
    if equipped_import["chest"] != "chest-aristocrat-coat":
        raise SystemExit("equipped import should fill unlocked chest from the save")
    if equipped_import["l1"] != "longsword":
        raise SystemExit("equipped import should fill unlocked L1 from the save")
    if equipped_import["l1Affinity"] != 100 or equipped_import["l1Upgrade"] != 10:
        raise SystemExit("equipped import should read Heavy +10 from the weapon id")
    if equipped_import["tal1"] != "crimson-amber-medallion":
        raise SystemExit("equipped import should fill unlocked talisman from the save")

    # --- Item Pool drawer ---
    print("\n--- item pool drawer ---")
    page.click("#toggle-item-pool-drawer")
    page.wait_for_timeout(200)
    drawer_visible = page.is_visible("#item-pool-drawer")
    print("Drawer visible after toggle:", drawer_visible)

    checklist_count_before = page.locator("#pool-checklist .pool-checklist-item").count()
    print("Armor tab (helm) checklist item count:", checklist_count_before)

    # Switch to weapons tab
    page.click('.tab-btn[data-tab="weapons"]')
    page.wait_for_timeout(200)
    weapons_checklist_count = page.locator("#pool-checklist .pool-checklist-item").count()
    print("Weapons tab checklist item count:", weapons_checklist_count)

    # Search within weapons tab
    page.fill("#pool-search", "sword")
    page.wait_for_timeout(200)
    filtered_count = page.locator("#pool-checklist .pool-checklist-item").count()
    print("Weapons tab filtered by 'sword':", filtered_count)

    # Exclude all filtered, verify weapon results panel shrinks
    page.click("#pool-select-none")
    page.wait_for_timeout(200)
    weapon_results_after_exclude = page.text_content("#weapon-results")
    print("'Sword' present in weapon results after excluding all matches:", "Sword" in weapon_results_after_exclude)
    count_label = page.text_content("#pool-count-label")
    print("Pool count label after select-none:", count_label)

    # Bring them back
    page.click("#pool-select-all")
    page.wait_for_timeout(200)
    count_label_after_all = page.text_content("#pool-count-label")
    print("Pool count label after select-all:", count_label_after_all)

    # Switch to talismans tab, exclude one, verify it disappears from the picker
    page.click('.tab-btn[data-tab="talismans"]')
    page.wait_for_timeout(200)
    page.fill("#pool-search", "great-jar")
    page.wait_for_timeout(200)
    page.click("#pool-checklist .pool-checklist-item input[type=checkbox]")
    page.wait_for_timeout(200)
    page.click('[data-slot="tal2"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "great-jar")
    page.wait_for_timeout(200)
    picker_html = page.inner_html("#picker-list")
    print("Great-Jar excluded from picker (should be empty-ish):", picker_html.strip()[:200])
    page.click("#picker-close")

    # Reset all excludes
    page.click("#pool-reset")
    page.wait_for_timeout(200)
    page.click('[data-slot="tal2"]')
    page.wait_for_timeout(200)
    page.fill("#picker-search", "great-jar")
    page.wait_for_timeout(200)
    picker_html_after_reset = page.inner_html("#picker-list")
    print("Great-Jar back after reset:", "Great" in picker_html_after_reset)
    page.click("#picker-close")

    # Tarnished Edition is enabled by default (it's obtainable Tarnished Pack
    # DLC content, not special/hidden) — confirm the checkbox defaults to
    # checked and the TE tag shows up in the armor checklist (the drawer
    # checklist always lists every item regardless of source-checkbox state;
    # that checkbox instead controls whether isIncluded() feeds the item to
    # the optimizer/weapon rankings, toggled separately below).
    page.click('.tab-btn[data-tab="armor"]')
    page.wait_for_timeout(100)
    print("Tarnished Edition source checked by default:", page.is_checked("#source-tarnished-edition"))
    armor_checklist_html = page.inner_html("#pool-checklist")
    print("TE tag visible in armor checklist:", "source-tag-te" in armor_checklist_html)
    page.uncheck("#source-tarnished-edition")
    page.wait_for_timeout(200)
    page.check("#source-tarnished-edition")
    page.wait_for_timeout(200)

    # --- Area filter buttons (checkbox convenience) ---
    print("\n--- area filters ---")
    page.select_option("#pool-armor-slot", "helm")
    page.wait_for_timeout(200)
    area_buttons_html = page.inner_html("#pool-area-filters")
    print("Area filter row present:", "area-btn" in area_buttons_html)
    print("Starting Gear button present:", "Starting Gear" in area_buttons_html)
    print("Starting Gear listed before Limgrave:", area_buttons_html.find("Starting Gear") < area_buttons_html.find("Limgrave"))
    print("Limgrave button present:", "Limgrave" in area_buttons_html)
    print("Starting class picker present:", page.locator("#starting-class").count() > 0)
    class_options = page.locator("#starting-class option").all_text_contents()
    print("Heavy Knight class option present:", "Heavy Knight" in class_options)
    print("Idus Knight class option present:", "Idus Knight" in class_options)
    if "Heavy Knight" not in class_options:
        raise SystemExit("Class picker should include Heavy Knight")
    if "Idus Knight" not in class_options:
        raise SystemExit("Class picker should include Idus Knight")

    page.locator("#area-select-none").click()
    page.wait_for_timeout(150)
    page.locator(".area-btn", has_text="Limgrave").first.click()
    page.wait_for_timeout(200)
    limgrave_btn = page.locator(".area-btn", has_text="Limgrave").first
    print("Limgrave highlighted after None+click:", "area-btn-on" in (limgrave_btn.get_attribute("class") or ""))
    caelid_btn = page.locator(".area-btn", has_text="Caelid").first
    print("Caelid stays off:", "area-btn-off" in (caelid_btn.get_attribute("class") or ""))

    kaiden = page.locator("#pool-checklist .pool-checklist-item", has_text="Kaiden Helm").first
    print("Kaiden checked:", kaiden.locator("input").is_checked())
    broken = page.locator("#pool-checklist .pool-checklist-item", has_text="Broken Gold Mask").first
    print("Untagged TE helm still listed:", broken.count() > 0)
    print("Untagged TE helm unchecked:", not broken.locator("input").is_checked())
    redmane = page.locator("#pool-checklist .pool-checklist-item", has_text="Redmane").first
    print("Caelid-only Redmane unchecked:", not redmane.locator("input").is_checked())
    if redmane.locator("input").is_disabled():
        raise SystemExit("region chips should not disable item checkboxes")
    redmane.locator("input").check()
    page.wait_for_timeout(150)
    redmane_over = page.evaluate(
        """() => {
      const a = ARMOR.find(x => x.slot === "helm" && x.name.includes("Redmane"));
      return { name: a && a.name, inPool: a && isIncluded(a, "armor") };
    }"""
    )
    print("Override-included Caelid helm:", redmane_over)
    if not redmane_over["inPool"]:
        raise SystemExit("checking a Caelid item should include it even when Caelid is off")
    redmane.locator("input").uncheck()
    page.wait_for_timeout(100)

    champ = page.evaluate(
        """() => {
      const c = ARMOR.find(a => a.name === "Champion Headband");
      return { areas: c.areas, inPool: isIncluded(c, "armor") };
    }"""
    )
    print("Champion Headband areas:", champ["areas"])
    print("Champion Headband in Limgrave-only pool:", champ["inPool"])
    if champ["inPool"]:
        raise SystemExit("Limgrave-only pool should not include Champion Headband")
    if "Starting Gear" not in champ["areas"] or "Caelid" not in champ["areas"]:
        raise SystemExit("Champion Headband should be Starting Gear and Caelid")

    maus = page.evaluate(
        """() => {
      const names = [
        "Mausoleum Knight Armor",
        "Mausoleum Knight Armor (Altered)",
        "Mausoleum Knight Gauntlets",
        "Mausoleum Knight Greaves",
      ];
      return Object.fromEntries(names.map(n => {
        const a = ARMOR.find(x => x.name === n);
        return [n, a ? a.areas : null];
      }));
    }"""
    )
    print("Mausoleum Knight areas:", maus)
    for name, areas in maus.items():
        if not areas or "Liurnia of the Lakes" not in areas:
            raise SystemExit(f"{name} should be tagged Liurnia of the Lakes")
        if "Weeping Peninsula" in areas:
            raise SystemExit(f"{name} should not be tagged Weeping Peninsula")

    page.locator(".area-btn", has_text="Starting Gear").first.click()
    page.wait_for_timeout(150)
    champ_on = page.evaluate("() => isIncluded(ARMOR.find(a => a.name === 'Champion Headband'), 'armor')")
    print("Champion Headband after enabling Starting Gear:", champ_on)
    if not champ_on:
        raise SystemExit("Starting Gear should include Champion Headband")
    page.locator(".area-btn", has_text="Starting Gear").first.click()
    page.wait_for_timeout(150)
    page.locator(".area-btn", has_text="Caelid").first.click()
    page.wait_for_timeout(150)
    champ_caelid = page.evaluate("() => isIncluded(ARMOR.find(a => a.name === 'Champion Headband'), 'armor')")
    print("Champion Headband with Caelid on, Starting Gear off:", champ_caelid)
    if not champ_caelid:
        raise SystemExit("Caelid access should include Champion Headband even with Starting Gear off")
    page.locator(".area-btn", has_text="Caelid").first.click()
    page.wait_for_timeout(150)

    bk = page.evaluate(
        """() => {
      const un = ARMOR.find(a => a.name === "Banished Knight Armor");
      const al = ARMOR.find(a => a.name === "Banished Knight Armor (Altered)");
      const helmUn = ARMOR.find(a => a.name === "Banished Knight Helm");
      const helmAl = ARMOR.find(a => a.name === "Banished Knight Helm (Altered)");
      return {
        includeAltered: document.getElementById("include-altered").checked,
        unAreas: un.areas,
        alAreas: al.areas,
        unIn: isIncluded(un, "armor"),
        alIn: isIncluded(al, "armor"),
        helmUnAreas: helmUn.areas,
        helmAlAreas: helmAl.areas,
        helmUnIn: isIncluded(helmUn, "armor"),
        helmAlIn: isIncluded(helmAl, "armor"),
      };
    }"""
    )
    print("Include altered checked by default:", bk["includeAltered"])
    print("Banished Knight Armor areas:", bk["unAreas"])
    print("Banished Knight Armor (Altered) areas:", bk["alAreas"])
    print("Unaltered chest in Limgrave-only pool:", bk["unIn"])
    print("Altered chest in Limgrave-only pool:", bk["alIn"])
    print("Unaltered helm areas:", bk["helmUnAreas"])
    print("Altered helm areas:", bk["helmAlAreas"])
    if not bk["includeAltered"]:
        raise SystemExit("include-altered should be on so both variants can be recommended")
    if "Limgrave" in bk["unAreas"]:
        raise SystemExit("unaltered Banished Knight Armor is not a Limgrave drop")
    if "Limgrave" not in bk["alAreas"]:
        raise SystemExit("Banished Knight Armor (Altered) should be obtainable in Limgrave")
    if "Caelid" not in bk["alAreas"]:
        raise SystemExit("Banished Knight Armor (Altered) also drops at Cathedral of Dragon Communion")
    if bk["unIn"]:
        raise SystemExit("Limgrave-only pool should not include unaltered Banished Knight Armor")
    if not bk["alIn"]:
        raise SystemExit("Limgrave-only pool should include Banished Knight Armor (Altered)")
    if "Limgrave" in bk["helmUnAreas"]:
        raise SystemExit("unaltered Banished Knight Helm is not a Limgrave drop")
    if "Limgrave" not in bk["helmAlAreas"]:
        raise SystemExit("Banished Knight Helm (Altered) should be obtainable in Limgrave")

    # Uncheck one Limgrave helm by hand -> Limgrave chip stays on (bulk helper,
    # not a lock). The helm leaves the pool until you check it again.
    kaiden.locator("input").uncheck()
    page.wait_for_timeout(150)
    limgrave_btn = page.locator(".area-btn", has_text="Limgrave").first
    print("Limgrave chip stays on after unchecking one item:", "area-btn-on" in (limgrave_btn.get_attribute("class") or ""))
    kaiden_in = page.evaluate("() => isIncluded(ARMOR.find(a => a.name === 'Kaiden Helm'), 'armor')")
    print("Kaiden Helm excluded from pool:", not kaiden_in)
    kaiden.locator("input").check()
    page.wait_for_timeout(150)
    limgrave_btn = page.locator(".area-btn", has_text="Limgrave").first
    print("Limgrave highlight still on after rechecking:", "area-btn-on" in (limgrave_btn.get_attribute("class") or ""))

    page.locator("#area-select-none").click()
    page.wait_for_timeout(150)
    page.select_option("#starting-class", "Hero")
    page.wait_for_timeout(200)
    sg_btn = page.locator(".area-btn", has_text="Starting Gear").first
    print("Starting Gear on after picking Hero:", "area-btn-on" in (sg_btn.get_attribute("class") or ""))
    if "area-btn-on" not in (sg_btn.get_attribute("class") or ""):
        raise SystemExit("Picking a class should turn Starting Gear on")
    class_pool = page.evaluate(
        """() => {
      const names = ["Champion Headband", "Bandit Mask", "Vagabond Knight Helm", "Kaiden Helm"];
      const armor = Object.fromEntries(names.map(n => {
        const a = ARMOR.find(x => x.name === n);
        return [n, { inPool: isIncluded(a, "armor"), classes: a.startingClasses || [] }];
      }));
      const axe = WEAPONS.find(w => w.name === "Battle Axe");
      const seal = WEAPONS.find(w => w.name === "Finger Seal");
      const longbow = WEAPONS.find(w => w.name === "Longbow");
      return {
        armor,
        axe: { inPool: isIncluded(axe, "weapons"), classes: axe.startingClasses || [] },
        seal: { inPool: isIncluded(seal, "weapons"), classes: seal.startingClasses || [] },
        longbow: { inPool: isIncluded(longbow, "weapons"), classes: longbow.startingClasses || [], areas: longbow.areas },
      };
    }"""
    )
    print("Hero class tags:", class_pool)
    champ_hero = class_pool["armor"]["Champion Headband"]
    bandit_hero = class_pool["armor"]["Bandit Mask"]
    vagabond_hero = class_pool["armor"]["Vagabond Knight Helm"]
    kaiden_hero = class_pool["armor"]["Kaiden Helm"]
    if champ_hero["classes"] != ["Hero"]:
        raise SystemExit("Champion Headband should be tagged as Hero starting gear")
    if "Bandit" not in bandit_hero["classes"]:
        raise SystemExit("Bandit Mask should be tagged as Bandit starting gear")
    if not champ_hero["inPool"]:
        raise SystemExit("Hero + Starting Gear should include Champion Headband")
    if bandit_hero["inPool"]:
        raise SystemExit("Hero + Starting Gear (Limgrave off) should exclude Bandit Mask")
    if vagabond_hero["inPool"]:
        raise SystemExit("Hero + Starting Gear should exclude Vagabond Knight Helm")
    if kaiden_hero["inPool"]:
        raise SystemExit("Hero + Starting Gear should exclude Kaiden Helm")
    if not class_pool["axe"]["inPool"]:
        raise SystemExit("Hero + Starting Gear should include Battle Axe")
    if class_pool["seal"]["inPool"]:
        raise SystemExit("Hero + Starting Gear should exclude Finger Seal")
    if "Limgrave" not in class_pool["longbow"]["areas"]:
        raise SystemExit("Longbow should also be obtainable in Limgrave")
    if class_pool["longbow"]["inPool"]:
        raise SystemExit("Hero + Starting Gear only should exclude Longbow")

    page.locator("#area-select-all").click()
    page.wait_for_timeout(150)
    longbow_all = page.evaluate("() => isIncluded(WEAPONS.find(w => w.name === 'Longbow'), 'weapons')")
    print("Longbow in pool with Hero + all regions:", longbow_all)
    if not longbow_all:
        raise SystemExit("Hero + all regions should include Longbow (Limgrave merchant)")

    page.locator("#area-select-none").click()
    page.wait_for_timeout(150)
    page.select_option("#starting-class", "Heavy Knight")
    page.wait_for_timeout(150)
    heavy = page.evaluate(
        """() => {
      const steel = ARMOR.find(a => a.name === "Steel Helm");
      const silver = ARMOR.find(a => a.name === "Silver Grooved Helm");
      const scim = WEAPONS.find(w => w.name === "Hefty Scimitar");
      const idus = WEAPONS.find(w => w.name === "Idus Sword");
      return {
        steel: { inPool: isIncluded(steel, "armor"), classes: steel.startingClasses || [], areas: steel.areas },
        silver: { inPool: isIncluded(silver, "armor"), classes: silver.startingClasses || [] },
        scim: { inPool: isIncluded(scim, "weapons"), classes: scim.startingClasses || [], areas: scim.areas },
        idus: { inPool: isIncluded(idus, "weapons") },
      };
    }"""
    )
    print("Heavy Knight kit:", heavy)
    if heavy["steel"]["classes"] != ["Heavy Knight"]:
        raise SystemExit("Steel Helm should be tagged as Heavy Knight starting gear")
    if heavy["scim"]["classes"] != ["Heavy Knight"]:
        raise SystemExit("Hefty Scimitar should be tagged as Heavy Knight starting gear")
    if "Starting Gear" not in heavy["steel"]["areas"] or "Weeping Peninsula" not in heavy["steel"]["areas"]:
        raise SystemExit("Steel Helm should be Starting Gear and Weeping Peninsula")
    if "Starting Gear" not in heavy["scim"]["areas"] or "Limgrave" not in heavy["scim"]["areas"]:
        raise SystemExit("Hefty Scimitar should be Starting Gear and Limgrave")
    if not heavy["steel"]["inPool"] or not heavy["scim"]["inPool"]:
        raise SystemExit("Heavy Knight + Starting Gear should include the Steel set and Hefty Scimitar")
    if heavy["silver"]["inPool"] or heavy["idus"]["inPool"]:
        raise SystemExit("Heavy Knight + Starting Gear should exclude the Idus Knight kit")

    page.select_option("#starting-class", "Idus Knight")
    page.wait_for_timeout(150)
    idus = page.evaluate(
        """() => {
      const silver = ARMOR.find(a => a.name === "Silver Grooved Helm");
      const steel = ARMOR.find(a => a.name === "Steel Helm");
      const sword = WEAPONS.find(w => w.name === "Idus Sword");
      const shield = WEAPONS.find(w => w.name === "Silver Grooved Shield");
      const scim = WEAPONS.find(w => w.name === "Hefty Scimitar");
      return {
        silver: { inPool: isIncluded(silver, "armor"), classes: silver.startingClasses || [], areas: silver.areas },
        steel: { inPool: isIncluded(steel, "armor") },
        sword: { inPool: isIncluded(sword, "weapons"), classes: sword.startingClasses || [] },
        shield: { inPool: isIncluded(shield, "weapons"), classes: shield.startingClasses || [] },
        scim: { inPool: isIncluded(scim, "weapons") },
      };
    }"""
    )
    print("Idus Knight kit:", idus)
    if idus["silver"]["classes"] != ["Idus Knight"]:
        raise SystemExit("Silver Grooved Helm should be tagged as Idus Knight starting gear")
    if idus["sword"]["classes"] != ["Idus Knight"] or idus["shield"]["classes"] != ["Idus Knight"]:
        raise SystemExit("Idus Sword and Silver Grooved Shield should be tagged as Idus Knight starting gear")
    if "Starting Gear" not in idus["silver"]["areas"] or "Liurnia of the Lakes" not in idus["silver"]["areas"]:
        raise SystemExit("Silver Grooved Helm should be Starting Gear and Liurnia")
    if not idus["silver"]["inPool"] or not idus["sword"]["inPool"] or not idus["shield"]["inPool"]:
        raise SystemExit("Idus Knight + Starting Gear should include the Silver Grooved kit and Idus Sword")
    if idus["steel"]["inPool"] or idus["scim"]["inPool"]:
        raise SystemExit("Idus Knight + Starting Gear should exclude the Heavy Knight kit")

    page.select_option("#starting-class", "")
    page.wait_for_timeout(150)
    any_class = page.evaluate(
        """() => ({
      champ: isIncluded(ARMOR.find(a => a.name === "Champion Headband"), "armor"),
      bandit: isIncluded(ARMOR.find(a => a.name === "Bandit Mask"), "armor"),
      seal: isIncluded(WEAPONS.find(w => w.name === "Finger Seal"), "weapons"),
    })"""
    )
    print("Any class + Starting Gear:", any_class)
    if not any_class["champ"] or not any_class["bandit"] or not any_class["seal"]:
        raise SystemExit("Any class should include every Starting Gear kit")

    page.locator("#area-select-all").click()
    page.wait_for_timeout(200)
    print("All restores TE helm checkbox:", page.locator("#pool-checklist .pool-checklist-item", has_text="Broken Gold Mask").locator("input").is_checked())

    print("DLC region buttons still dashed:", "area-btn-dlc" in page.inner_html("#pool-area-filters"))
    print("Starting Gear chip is dotted:", "area-btn-meta" in page.inner_html("#pool-area-filters"))

    browser.close()

print("\n=== CONSOLE/PAGE ERRORS ===")
if errors:
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("None")
