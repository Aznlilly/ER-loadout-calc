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

    # Uncheck one Limgrave helm by hand -> Limgrave chip stays on (access
    # filter, not a bulk checkbox). The helm leaves the pool.
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
      return {
        armor,
        axe: { inPool: isIncluded(axe, "weapons"), classes: axe.startingClasses || [] },
        seal: { inPool: isIncluded(seal, "weapons"), classes: seal.startingClasses || [] },
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
