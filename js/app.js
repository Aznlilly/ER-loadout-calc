// app.js — UI glue: loads data, equipment board, optimizer, results.

let ARMOR = [];
let WEAPONS = [];
let TALISMANS = [];
let EQUIP_LOAD_TABLE = {};
let ARMOR_BY_ID = new Map();
let WEAPONS_BY_ID = new Map();
let TALISMANS_BY_ID = new Map();
let GAME_IDS = { weapons: {}, armor: {}, talismans: {} };
let WEAPON_VARIANTS = {};
let OWNED_WEAPON_INSTANCES = {};

const ARMOR_SLOTS = ["helm", "chest", "gauntlets", "legs"];
const WEAPON_SLOTS_LEFT = ["l1", "l2", "l3"];
const WEAPON_SLOTS_RIGHT = ["r1", "r2", "r3"];
const WEAPON_SLOTS = ["r1", "r2", "r3", "l1", "l2", "l3"];
const TALISMAN_SLOTS = ["tal1", "tal2", "tal3", "tal4"];
const ALL_SLOTS = [...ARMOR_SLOTS, ...WEAPON_SLOTS, ...TALISMAN_SLOTS];
const STORAGE_KEY = "er-loadout-equip-v1";
const LOAD_RATIO_MIN = 0.05;
const LOAD_RATIO_MAX = 1.2;
const LOAD_RATIO_SLIDER_SCALE = 1000; // slider stores tenths of a percent

const SLOT_LABELS = {
  helm: "Helm",
  chest: "Chest",
  gauntlets: "Gauntlets",
  legs: "Legs",
  r1: "R1",
  r2: "R2",
  r3: "R3",
  l1: "L1",
  l2: "L2",
  l3: "L3",
  tal1: "Talisman 1",
  tal2: "Talisman 2",
  tal3: "Talisman 3",
  tal4: "Talisman 4",
};

function emptySlot() {
  return { id: null, locked: false, affinity: 0, upgrade: 0 };
}

let EQUIPMENT = Object.fromEntries(ALL_SLOTS.map((s) => [s, emptySlot()]));
let talismanSlotCount = 4;
let loadRatio = 0.699;
let pickerSlot = null;
let characterGender = "male";

const EXCLUDED = {
  armor: new Set(),
  weapons: new Set(),
  talismans: new Set(),
};

function emptyForced() {
  return {
    armor: { include: new Set(), exclude: new Set() },
    weapons: { include: new Set(), exclude: new Set() },
    talismans: { include: new Set(), exclude: new Set() },
  };
}
let FORCED = emptyForced();

let poolActiveTab = "armor";

const DLC_REGIONS = new Set([
  "Gravesite Plain", "Scadu Altus", "Ancient Ruins of Rauh", "Cerulean Coast",
  "Charo's Hidden Grave", "Jagged Peak", "Abyssal Woods", "Scaduview",
  "Shadow Keep", "Enir-Ilim", "Belurat, Tower Settlement",
]);
const STARTING_GEAR_REGION = "Starting Gear";
const META_REGIONS = new Set([STARTING_GEAR_REGION]);
const MASTER_REGION_ORDER = [
  STARTING_GEAR_REGION,
  "Limgrave", "Weeping Peninsula", "Liurnia of the Lakes", "Caelid", "Dragonbarrow",
  "Altus Plateau", "Mt. Gelmir", "Capital Outskirts", "Leyndell, Royal Capital",
  "Mountaintops of the Giants", "Consecrated Snowfield", "Miquella's Haligtree",
  "Crumbling Farum Azula", "Siofra River", "Ainsel River", "Lake of Rot",
  "Nokron, Eternal City", "Nokstella, Eternal City", "Deeproot Depths",
  "Mohgwyn Palace", "Leyndell, Ashen Capital", "Roundtable Hold",
  ...DLC_REGIONS,
];
const selectedRegions = new Set(MASTER_REGION_ORDER);
const STARTING_CLASS_ORDER = [
  "Vagabond", "Warrior", "Hero", "Bandit", "Astrologer",
  "Prophet", "Samurai", "Prisoner", "Confessor", "Wretch",
  "Heavy Knight", "Idus Knight",
];
let selectedStartingClass = "";

const SOURCE_CHECKBOX_IDS = {
  "Elden Ring": "source-elden-ring",
  "Shadow of the Erdtree": "source-shadow-of-the-erdtree",
  "Tarnished Edition": "source-tarnished-edition",
};

const SOURCE_TAGS = {
  "Elden Ring": "",
  "Shadow of the Erdtree": "SotE",
  "Tarnished Edition": "TE",
};

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function itemIconSrc(item) {
  if (!item) return "";
  if (characterGender === "female" && item.iconFemale) return item.iconFemale;
  return item.icon || "";
}

function iconHtml(item, extraClass) {
  const cls = extraClass || "slot-icon";
  const src = itemIconSrc(item);
  if (src) {
    const idAttr = item.id ? ` data-item-id="${escapeHtml(item.id)}"` : "";
    return `<img class="${cls}"${idAttr} src="${escapeHtml(src)}" alt="" onerror="this.outerHTML='<span class=&quot;slot-placeholder&quot;></span>'">`;
  }
  return `<span class="slot-placeholder"></span>`;
}

function setCharacterGender(gender) {
  characterGender = gender === "female" ? "female" : "male";
  const sel = document.getElementById("character-gender");
  if (sel && sel.value !== characterGender) sel.value = characterGender;
  saveState();
  renderEquipment();
  renderWeaponResults();
  if (pickerSlot) renderPickerList();
  document.querySelectorAll("img[data-item-id]").forEach((img) => {
    const item = ARMOR_BY_ID.get(img.dataset.itemId)
      || WEAPONS_BY_ID.get(img.dataset.itemId)
      || TALISMANS_BY_ID.get(img.dataset.itemId);
    const src = itemIconSrc(item);
    if (src) img.src = src;
  });
}

const WIKI_BASE = "https://eldenring.wiki.fextralife.com/";

function wikiUrl(item) {
  if (item && item.wiki) return item.wiki;
  const slug = String((item && item.name) || "").replace(/ /g, "_");
  return WIKI_BASE + encodeURIComponent(slug);
}

function armorDisplayName(item, slot) {
  const name = (item && item.name) || "";
  if (item && item.altered && !/\(altered\)/i.test(name)) return `${name} (Altered)`;
  if (slot && slotKind(slot) === "weapon" && item) {
    const aff = EQUIPMENT[slot] && EQUIPMENT[slot].affinity;
    const up = EQUIPMENT[slot] && EQUIPMENT[slot].upgrade;
    const includeUpgrades = document.getElementById("include-upgrades")?.checked;
    const includeAffinities = document.getElementById("include-affinities")?.checked;
    if ((includeAffinities && aff) || (includeUpgrades && up)) {
      return variantDisplayName(item, includeAffinities ? aff : 0, includeUpgrades ? up : 0, includeUpgrades);
    }
  }
  return name;
}

function sourceCellHtml(item) {
  const label = (item.areas && item.areas.length) ? item.areas.join(", ") : "—";
  return `<a class="wiki-link" href="${escapeHtml(wikiUrl(item))}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

function slotKind(slot) {
  if (ARMOR_SLOTS.includes(slot)) return "armor";
  if (WEAPON_SLOTS.includes(slot)) return "weapon";
  return "talisman";
}

function defaultMetaForPicker(id) {
  if (!pickerSlot || slotKind(pickerSlot) !== "weapon") return undefined;
  const owned = OWNED_WEAPON_INSTANCES[id] || [];
  if (!owned.length) return { affinity: 0, upgrade: 0 };
  let best = owned[0];
  for (const o of owned) {
    if ((o.upgrade || 0) > (best.upgrade || 0)) best = o;
  }
  return { affinity: best.affinity || 0, upgrade: best.upgrade || 0 };
}

function weaponRankOpts(extra) {
  return {
    includeAffinities: document.getElementById("include-affinities").checked,
    includeUpgrades: document.getElementById("include-upgrades").checked,
    variants: WEAPON_VARIANTS,
    ownedInstances: OWNED_WEAPON_INSTANCES,
    ...(extra || {}),
  };
}

function weaponSuggestKey(row, includeAffinities) {
  if (!row || !row.weapon) return "";
  return includeAffinities ? `${row.weapon.id}:${row.affinity || 0}` : row.weapon.id;
}

function buildIndexes() {
  ARMOR_BY_ID = new Map(ARMOR.map((a) => [a.id, a]));
  WEAPONS_BY_ID = new Map(WEAPONS.map((w) => [w.id, w]));
  TALISMANS_BY_ID = new Map(TALISMANS.map((t) => [t.id, t]));
}

function itemForSlot(slot) {
  const id = EQUIPMENT[slot] && EQUIPMENT[slot].id;
  if (!id) return null;
  const kind = slotKind(slot);
  if (kind === "armor") return ARMOR_BY_ID.get(id) || null;
  if (kind === "weapon") return WEAPONS_BY_ID.get(id) || null;
  return TALISMANS_BY_ID.get(id) || null;
}

function activeTalismanSlots() {
  return TALISMAN_SLOTS.slice(0, talismanSlotCount);
}

function isTalismanSlotActive(slot) {
  return activeTalismanSlots().includes(slot);
}

async function loadData() {
  const [armor, weapons, talismans, equipLoadTable, gameIds, weaponVariants] = await Promise.all([
    fetch("data/armor.json").then((r) => r.json()),
    fetch("data/weapons.json").then((r) => r.json()),
    fetch("data/talismans.json").then((r) => r.json()),
    fetch("data/equip_load_table.json").then((r) => r.json()),
    fetch("data/game_ids.json").then((r) => r.json()).catch(() => ({ weapons: {}, armor: {}, talismans: {} })),
    fetch("data/weapon_variants.json").then((r) => r.json()).catch(() => ({})),
  ]);
  ARMOR = armor;
  WEAPONS = weapons;
  TALISMANS = talismans;
  EQUIP_LOAD_TABLE = equipLoadTable;
  GAME_IDS = gameIds;
  WEAPON_VARIANTS = weaponVariants;
  buildIndexes();
}

function getStats() {
  return {
    vig: parseInt(document.getElementById("stat-vig").value) || 0,
    mind: parseInt(document.getElementById("stat-min").value) || 0,
    end: parseInt(document.getElementById("stat-end").value) || 0,
    str: parseInt(document.getElementById("stat-str").value) || 0,
    dex: parseInt(document.getElementById("stat-dex").value) || 0,
    int: parseInt(document.getElementById("stat-int").value) || 0,
    fai: parseInt(document.getElementById("stat-fai").value) || 0,
    arc: parseInt(document.getElementById("stat-arc").value) || 0,
  };
}

function computeLevel(stats) {
  const sum = stats.vig + stats.mind + stats.end + stats.str + stats.dex + stats.int + stats.fai + stats.arc;
  return sum - 79;
}

function updateDerivedCharacterInfo() {
  const stats = getStats();
  document.getElementById("derived-level").textContent = Math.max(1, computeLevel(stats));
  const baseLoad = baseEquipLoadForEndurance(stats.end, EQUIP_LOAD_TABLE);
  document.getElementById("derived-base-load").textContent = baseLoad.toFixed(1);
  updateLoadBudgetDisplay();
  updateEquipLoadReadout();
}

function sourceEnabled(source) {
  const id = SOURCE_CHECKBOX_IDS[source];
  const el = id && document.getElementById(id);
  return el ? el.checked : true;
}

function allRegionsSelected() {
  return MASTER_REGION_ORDER.every((r) => selectedRegions.has(r));
}

function areaMatchesFilter(area, item) {
  if (!selectedRegions.has(area)) return false;
  if (area === STARTING_GEAR_REGION && selectedStartingClass) {
    return (item.startingClasses || []).includes(selectedStartingClass);
  }
  return true;
}

function matchesRegionFilter(item) {
  if (selectedRegions.size === 0) return false;
  const areas = item.areas || [];
  if (allRegionsSelected() && !areas.length) return true;
  if (!areas.length) return false;
  return areas.some((a) => areaMatchesFilter(a, item));
}

function isIncluded(item, type) {
  return sourceEnabled(item.source) && !EXCLUDED[type].has(item.id);
}

function setPoolItemIncluded(type, item, included) {
  const forced = FORCED[type];
  if (included) {
    EXCLUDED[type].delete(item.id);
    forced.exclude.delete(item.id);
    if (!matchesRegionFilter(item)) forced.include.add(item.id);
    else forced.include.delete(item.id);
  } else {
    EXCLUDED[type].add(item.id);
    forced.include.delete(item.id);
    if (matchesRegionFilter(item)) forced.exclude.add(item.id);
    else forced.exclude.delete(item.id);
  }
}

function applyRegionExclusions() {
  for (const type of ["armor", "weapons", "talismans"]) {
    const forced = FORCED[type];
    for (const it of poolItemsForType(type)) {
      if (forced.include.has(it.id)) {
        EXCLUDED[type].delete(it.id);
        continue;
      }
      if (forced.exclude.has(it.id)) {
        EXCLUDED[type].add(it.id);
        continue;
      }
      if (matchesRegionFilter(it)) EXCLUDED[type].delete(it.id);
      else EXCLUDED[type].add(it.id);
    }
  }
}

function includeAllPoolItems() {
  EXCLUDED.armor.clear();
  EXCLUDED.weapons.clear();
  EXCLUDED.talismans.clear();
  FORCED = emptyForced();
}

function selectAllRegions() {
  MASTER_REGION_ORDER.forEach((r) => selectedRegions.add(r));
}

function selectNoRegions() {
  selectedRegions.clear();
}

function allPoolItemsIncluded() {
  return allRegionsSelected()
    && EXCLUDED.armor.size === 0
    && EXCLUDED.weapons.size === 0
    && EXCLUDED.talismans.size === 0;
}

function itemsInRegion(region) {
  const out = [];
  for (const type of ["armor", "weapons", "talismans"]) {
    for (const it of poolItemsForType(type)) {
      if ((it.areas || []).includes(region)) out.push({ type, item: it });
    }
  }
  return out;
}

function sourceTagHtml(source) {
  const tag = SOURCE_TAGS[source];
  return tag ? ` <span class="source-tag source-tag-${tag.toLowerCase()}">${tag}</span>` : "";
}

function getSelectedTalismans() {
  return activeTalismanSlots()
    .map((s) => itemForSlot(s))
    .filter(Boolean);
}

function getEquippedWeapons() {
  return WEAPON_SLOTS.map((s) => itemForSlot(s)).filter(Boolean);
}

function getEquippedArmor() {
  return ARMOR_SLOTS.map((s) => itemForSlot(s)).filter(Boolean);
}

const STAT_INPUT_IDS = {
  vig: "stat-vig",
  mind: "stat-min",
  end: "stat-end",
  str: "stat-str",
  dex: "stat-dex",
  int: "stat-int",
  fai: "stat-fai",
  arc: "stat-arc",
};

function clampInt(n, min, max) {
  const v = parseInt(n, 10);
  if (!Number.isFinite(v)) return null;
  return Math.max(min, Math.min(max, v));
}

function readSave() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    return data && typeof data === "object" ? data : null;
  } catch (_) {
    return null;
  }
}

function saveState() {
  const payload = {
    slots: EQUIPMENT,
    talismanSlotCount,
    stats: getStats(),
    loadRatio,
    goal: document.querySelector('input[name="goal"]:checked')?.value,
    resistanceStat: document.getElementById("resistance-stat").value,
    damageType: document.getElementById("damage-type").value,
    minweightMetric: document.getElementById("minweight-metric").value,
    minweightTarget: document.getElementById("minweight-target").value,
    gender: characterGender,
    twoHanding: document.getElementById("weapon-two-hand").checked,
    onlyMeetable: document.getElementById("weapon-only-meetable").checked,
    weaponCategory: document.getElementById("weapon-category").value,
    includeAltered: document.getElementById("include-altered").checked,
    includeAffinities: document.getElementById("include-affinities").checked,
    includeUpgrades: document.getElementById("include-upgrades").checked,
    ownedWeaponInstances: OWNED_WEAPON_INSTANCES,
    sources: Object.fromEntries(
      Object.entries(SOURCE_CHECKBOX_IDS).map(([source, id]) => {
        const el = document.getElementById(id);
        return [source, el ? el.checked : true];
      })
    ),
    startingClass: selectedStartingClass,
    regions: [...selectedRegions],
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (_) { /* ignore quota / private mode */ }
}

function saveEquipment() {
  saveState();
}

function applySavedWeaponCategory(data) {
  if (!data || data.weaponCategory == null) return;
  const sel = document.getElementById("weapon-category");
  if (!sel) return;
  if ([...sel.options].some((o) => o.value === data.weaponCategory)) {
    sel.value = data.weaponCategory;
  }
}

function loadSavedState() {
  const data = readSave();
  if (!data) return;

  if (data.talismanSlotCount >= 1 && data.talismanSlotCount <= 4) {
    talismanSlotCount = data.talismanSlotCount;
    const sel = document.getElementById("talisman-slot-count");
    if (sel) sel.value = String(talismanSlotCount);
  }
  if (data.slots) {
    for (const slot of ALL_SLOTS) {
      const saved = data.slots[slot];
      if (!saved) continue;
      const id = saved.id || null;
      const item = id && (
        ARMOR_BY_ID.get(id) || WEAPONS_BY_ID.get(id) || TALISMANS_BY_ID.get(id)
      );
      EQUIPMENT[slot] = {
        id: item ? id : null,
        locked: !!saved.locked,
        affinity: item && saved.affinity ? saved.affinity : 0,
        upgrade: item && saved.upgrade ? saved.upgrade : 0,
      };
    }
  }

  if (data.stats && typeof data.stats === "object") {
    for (const [key, id] of Object.entries(STAT_INPUT_IDS)) {
      const v = clampInt(data.stats[key], 1, 99);
      if (v != null) document.getElementById(id).value = String(v);
    }
  }

  if (data.loadRatio != null) applyLoadRatio(data.loadRatio);

  if (["poise", "negation", "damage", "resistance", "minweight"].includes(data.goal)) {
    const radio = document.querySelector(`input[name="goal"][value="${data.goal}"]`);
    if (radio) radio.checked = true;
  }
  if (data.resistanceStat) {
    const sel = document.getElementById("resistance-stat");
    if ([...sel.options].some((o) => o.value === data.resistanceStat)) sel.value = data.resistanceStat;
  }
  if (data.damageType) {
    const sel = document.getElementById("damage-type");
    if ([...sel.options].some((o) => o.value === data.damageType)) sel.value = data.damageType;
  }
  if (data.minweightMetric) {
    const sel = document.getElementById("minweight-metric");
    if ([...sel.options].some((o) => o.value === data.minweightMetric)) sel.value = data.minweightMetric;
  }
  if (data.minweightTarget != null && data.minweightTarget !== "") {
    document.getElementById("minweight-target").value = String(data.minweightTarget);
  }

  if (data.gender === "female" || data.gender === "male") {
    characterGender = data.gender;
    const sel = document.getElementById("character-gender");
    if (sel) sel.value = characterGender;
  }

  if (typeof data.twoHanding === "boolean") {
    document.getElementById("weapon-two-hand").checked = data.twoHanding;
  }
  if (typeof data.onlyMeetable === "boolean") {
    document.getElementById("weapon-only-meetable").checked = data.onlyMeetable;
  }
  if (typeof data.includeAltered === "boolean") {
    document.getElementById("include-altered").checked = data.includeAltered;
  }
  if (typeof data.includeAffinities === "boolean") {
    document.getElementById("include-affinities").checked = data.includeAffinities;
  }
  if (typeof data.includeUpgrades === "boolean") {
    document.getElementById("include-upgrades").checked = data.includeUpgrades;
  }
  if (data.ownedWeaponInstances && typeof data.ownedWeaponInstances === "object") {
    OWNED_WEAPON_INSTANCES = data.ownedWeaponInstances;
  }
  if (data.sources && typeof data.sources === "object") {
    for (const [source, id] of Object.entries(SOURCE_CHECKBOX_IDS)) {
      if (typeof data.sources[source] === "boolean") {
        document.getElementById(id).checked = data.sources[source];
      }
    }
  }

  if (data.startingClass === "" || STARTING_CLASS_ORDER.includes(data.startingClass)) {
    selectedStartingClass = data.startingClass;
  }
  if (Array.isArray(data.regions)) {
    selectedRegions.clear();
    for (const region of data.regions) {
      if (MASTER_REGION_ORDER.includes(region)) selectedRegions.add(region);
    }
  }
}

function setSlotItem(slot, id, meta) {
  if (slotKind(slot) === "talisman" && id) {
    for (const other of activeTalismanSlots()) {
      if (other !== slot && EQUIPMENT[other].id === id) {
        EQUIPMENT[other].id = EQUIPMENT[slot].id;
        EQUIPMENT[other].affinity = EQUIPMENT[slot].affinity;
        EQUIPMENT[other].upgrade = EQUIPMENT[slot].upgrade;
      }
    }
  }
  EQUIPMENT[slot].id = id;
  EQUIPMENT[slot].affinity = (meta && meta.affinity) || 0;
  EQUIPMENT[slot].upgrade = (meta && meta.upgrade) || 0;
  saveEquipment();
  renderEquipment();
  updateDerivedCharacterInfo();
}

function toggleLock(slot) {
  if (slotKind(slot) === "talisman" && !isTalismanSlotActive(slot)) return;
  EQUIPMENT[slot].locked = !EQUIPMENT[slot].locked;
  saveEquipment();
  renderEquipment();
}

function renderSlot(slot, inactive) {
  const item = inactive ? null : itemForSlot(slot);
  const locked = !inactive && EQUIPMENT[slot].locked;
  const classes = [
    "equip-slot",
    locked ? "locked" : "",
    inactive ? "inactive" : "",
    item ? "filled" : "",
  ].filter(Boolean).join(" ");
  const name = item ? escapeHtml(armorDisplayName(item, slot)) : "Empty";
  const weight = item ? `${item.weight}` : "";
  return `<div class="${classes}" data-slot="${slot}" role="button" tabindex="0" aria-label="${escapeHtml(SLOT_LABELS[slot])}${item ? ": " + escapeHtml(item.name) : ""}">
    <button type="button" class="lock-btn" data-lock="${slot}" title="${locked ? "Unlock this slot" : "Lock this slot"}" aria-pressed="${locked}" aria-label="${locked ? "Unlock" : "Lock"} ${escapeHtml(SLOT_LABELS[slot])}">${locked ? "Locked" : "Lock"}</button>
    <span class="slot-label">${escapeHtml(SLOT_LABELS[slot])}</span>
    ${iconHtml(item)}
    <span class="slot-name">${name}</span>
    <span class="slot-weight">${weight !== "" ? weight + " wt" : ""}</span>
  </div>`;
}

function renderEquipment() {
  const left = document.getElementById("equip-weapons-left");
  const armor = document.getElementById("equip-armor");
  const right = document.getElementById("equip-weapons-right");
  const tals = document.getElementById("equip-talismans");
  if (!left) return;
  left.innerHTML = WEAPON_SLOTS_LEFT.map((s) => renderSlot(s, false)).join("");
  armor.innerHTML = ARMOR_SLOTS.map((s) => renderSlot(s, false)).join("");
  right.innerHTML = WEAPON_SLOTS_RIGHT.map((s) => renderSlot(s, false)).join("");
  tals.innerHTML = TALISMAN_SLOTS.map((s) => renderSlot(s, !isTalismanSlotActive(s))).join("");
  updateEquipLoadReadout();
}

function updateEquipLoadReadout() {
  const el = document.getElementById("equip-current-load");
  if (!el) return;
  const { maxLoad, currentWeight, currentRatio } = getLoadBudget();
  const cls = loadClass(currentRatio);
  el.innerHTML = `${currentWeight.toFixed(1)} / ${maxLoad.toFixed(1)} <span class="badge ${cls}">${(currentRatio * 100).toFixed(1)}% ${cls}</span>`;
}

function pickerCandidates(slot) {
  const kind = slotKind(slot);
  const q = (document.getElementById("picker-search").value || "").toLowerCase();
  if (kind === "armor") {
    const includeAltered = document.getElementById("include-altered").checked;
    return ARMOR.filter((a) => a.slot === slot && isIncluded(a, "armor") && (includeAltered || !a.altered))
      .filter((a) => !q || a.name.toLowerCase().includes(q));
  }
  if (kind === "weapon") {
    return WEAPONS.filter((w) => isIncluded(w, "weapons"))
      .filter((w) => !q || w.name.toLowerCase().includes(q) || (w.category || "").toLowerCase().includes(q));
  }
  return TALISMANS.filter((t) => isIncluded(t, "talismans"))
    .filter((t) => !q || t.name.toLowerCase().includes(q) || (t.effect || "").toLowerCase().includes(q));
}

function renderPickerList() {
  if (!pickerSlot) return;
  const list = document.getElementById("picker-list");
  const items = pickerCandidates(pickerSlot).slice(0, 250);
  const currentId = EQUIPMENT[pickerSlot].id;
  list.innerHTML = "";
  for (const it of items) {
    const div = document.createElement("div");
    div.className = "pick-item picker-item" + (it.id === currentId ? " selected" : "");
    div.dataset.itemId = it.id;
    div.setAttribute("role", "button");
    div.tabIndex = 0;
    div.setAttribute("aria-label", it.name);
    const extra = slotKind(pickerSlot) === "talisman"
      ? `<span class="eff">${escapeHtml(it.effect || "")}</span>`
      : `<span class="eff">${it.weight} wt${it.category ? " · " + escapeHtml(it.category) : ""}</span>`;
    div.innerHTML = `${iconHtml(it)}<span>${escapeHtml(armorDisplayName(it))}${sourceTagHtml(it.source)} (${it.weight})</span>${extra}`;
    div.addEventListener("click", () => {
      setSlotItem(pickerSlot, it.id, defaultMetaForPicker(it.id));
      closePicker();
    });
    list.appendChild(div);
  }
  if (!items.length) {
    list.innerHTML = `<p class="hint">No matching items in the current item pool.</p>`;
  }
}

function openPicker(slot) {
  if (slotKind(slot) === "talisman" && !isTalismanSlotActive(slot)) return;
  pickerSlot = slot;
  document.getElementById("picker-title").textContent = `Choose ${SLOT_LABELS[slot]}`;
  document.getElementById("picker-search").value = "";
  document.getElementById("item-picker-overlay").classList.remove("hidden");
  renderPickerList();
  document.getElementById("picker-search").focus();
}

function closePicker() {
  pickerSlot = null;
  document.getElementById("item-picker-overlay").classList.add("hidden");
}

function unequipAll() {
  trackEvent("unequip-all");
  for (const slot of ALL_SLOTS) {
    if (EQUIPMENT[slot].locked) continue;
    EQUIPMENT[slot].id = null;
    EQUIPMENT[slot].affinity = 0;
    EQUIPMENT[slot].upgrade = 0;
  }
  saveEquipment();
  renderEquipment();
  updateDerivedCharacterInfo();
  renderWeaponResults();
}

function setupEquipmentBoard() {
  document.getElementById("equip-board").addEventListener("click", onEquipClick);
  document.getElementById("equip-talismans").addEventListener("click", onEquipClick);
  document.getElementById("equip-board").addEventListener("keydown", onEquipKey);
  document.getElementById("equip-talismans").addEventListener("keydown", onEquipKey);

  document.getElementById("talisman-slot-count").addEventListener("change", (e) => {
    const n = parseInt(e.target.value, 10);
    talismanSlotCount = Math.max(1, Math.min(4, n || 4));
    saveEquipment();
    renderEquipment();
    updateDerivedCharacterInfo();
  });

  document.getElementById("unequip-all").addEventListener("click", unequipAll);
  document.getElementById("include-altered").addEventListener("change", () => {
    saveState();
    if (pickerSlot) renderPickerList();
  });
  ["include-affinities", "include-upgrades"].forEach((id) => {
    document.getElementById(id).addEventListener("change", () => {
      saveState();
      renderEquipment();
      renderWeaponResults();
    });
  });
  document.getElementById("picker-search").addEventListener("input", renderPickerList);
  document.getElementById("picker-close").addEventListener("click", closePicker);
  document.getElementById("picker-unequip").addEventListener("click", () => {
    if (!pickerSlot) return;
    setSlotItem(pickerSlot, null);
    closePicker();
  });
  document.getElementById("item-picker-overlay").addEventListener("click", (e) => {
    if (e.target.id === "item-picker-overlay") closePicker();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && pickerSlot) closePicker();
  });
}

function onEquipClick(e) {
  const lockBtn = e.target.closest("[data-lock]");
  if (lockBtn) {
    e.preventDefault();
    e.stopPropagation();
    toggleLock(lockBtn.getAttribute("data-lock"));
    return;
  }
  const slotEl = e.target.closest("[data-slot]");
  if (slotEl && !slotEl.classList.contains("inactive")) {
    openPicker(slotEl.getAttribute("data-slot"));
  }
}

function onEquipKey(e) {
  if (e.key !== "Enter" && e.key !== " ") return;
  const slotEl = e.target.closest("[data-slot]");
  if (!slotEl || slotEl.classList.contains("inactive")) return;
  e.preventDefault();
  openPicker(slotEl.getAttribute("data-slot"));
}

function clampLoadRatio(raw) {
  const v = parseFloat(raw);
  if (!Number.isFinite(v)) return loadRatio;
  return Math.max(LOAD_RATIO_MIN, Math.min(LOAD_RATIO_MAX, v));
}

function sliderUnitsFromRatio(ratio) {
  return Math.round(ratio * LOAD_RATIO_SLIDER_SCALE);
}

function ratioFromSliderUnits(units) {
  return clampLoadRatio(parseFloat(units) / LOAD_RATIO_SLIDER_SCALE);
}

function applyLoadRatio(raw) {
  // Snap to 0.1% so the label, slider, and optimizer always agree.
  loadRatio = sliderUnitsFromRatio(clampLoadRatio(raw)) / LOAD_RATIO_SLIDER_SCALE;
  const el = document.getElementById("load-ratio");
  if (el) el.value = String(sliderUnitsFromRatio(loadRatio));
  const label = document.getElementById("load-ratio-value");
  if (label) label.textContent = `${(loadRatio * 100).toFixed(1)}%`;
}

function resultArmorWeight(result) {
  return totalWeight(ARMOR_SLOTS.map((s) => result && result.selection[s]).filter(Boolean));
}

function resultExceedsLoadCap(result, maxLoad, ratio, reservedWeight) {
  const armorW = resultArmorWeight(result);
  const total = armorW + reservedWeight;
  if (total > maxLoad * ratio + 1e-9) return true;
  if (maxLoad > 0 && isHeavierLoadClass(loadClass(total / maxLoad), allowedLoadClass(ratio))) {
    return true;
  }
  return false;
}

function optimizeArmorForLoad(pool, objective, requiredSlots) {
  const { maxLoad, ratio, talismanWeight, weaponWeight, budgetForArmor } = getLoadBudget();
  const reservedWeight = talismanWeight + weaponWeight;
  let budget = budgetForArmor;
  for (let i = 0; i < 30; i++) {
    const result = optimizeArmor(pool, objective, budget, requiredSlots);
    if (!result) return { result: null, maxLoad, budgetForArmor };
    if (!resultExceedsLoadCap(result, maxLoad, ratio, reservedWeight)) {
      return { result, maxLoad, budgetForArmor };
    }
    const armorW = resultArmorWeight(result);
    budget = Math.min(budget, armorW) - 0.1;
    if (budget < 0) break;
  }
  return { result: null, maxLoad, budgetForArmor };
}

function getLoadBudget() {
  const stats = getStats();
  const talismans = getSelectedTalismans();
  const weapons = getEquippedWeapons();
  const armor = getEquippedArmor();
  const maxLoad = computeMaxEquipLoad(stats.end, talismans, EQUIP_LOAD_TABLE);
  const ratio = loadRatio;
  const talismanWeight = totalWeight(talismans);
  const weaponWeight = totalWeight(weapons);
  const armorWeight = totalWeight(armor);
  const currentWeight = armorWeight + weaponWeight + talismanWeight;
  const budgetForArmor = Math.max(0, maxLoad * ratio - talismanWeight - weaponWeight);
  const currentRatio = maxLoad > 0 ? currentWeight / maxLoad : 0;
  return { maxLoad, ratio, talismanWeight, weaponWeight, armorWeight, currentWeight, currentRatio, budgetForArmor };
}

function isShield(item) {
  const cat = (item && (item.category || item.type)) || "";
  return /shield/i.test(cat);
}

function equippedWeaponWeightLabel(weapons, weaponWeight) {
  if (!weaponWeight) return "";
  const hasShield = weapons.some(isShield);
  const hasWeapon = weapons.some((w) => !isShield(w));
  if (hasShield && hasWeapon) return `${weaponWeight.toFixed(1)} weapon/shield`;
  if (hasShield) return `${weaponWeight.toFixed(1)} shield`;
  return `${weaponWeight.toFixed(1)} weapon`;
}

function updateLoadBudgetDisplay() {
  const { maxLoad, budgetForArmor, talismanWeight, weaponWeight } = getLoadBudget();
  document.getElementById("derived-maxload").textContent = maxLoad.toFixed(1);
  const parts = [];
  if (talismanWeight) parts.push(`${talismanWeight.toFixed(1)} talisman`);
  const weaponPart = equippedWeaponWeightLabel(getEquippedWeapons(), weaponWeight);
  if (weaponPart) parts.push(weaponPart);
  const after = parts.length ? ` (after ${parts.join(" + ")})` : "";
  document.getElementById("derived-budget").textContent = `${budgetForArmor.toFixed(1)}${after}`;
  updateEquipLoadReadout();
}

function getArmorPool() {
  const includeAltered = document.getElementById("include-altered").checked;
  const pool = { helm: [], chest: [], gauntlets: [], legs: [] };
  for (const a of ARMOR) {
    if (!isIncluded(a, "armor")) continue;
    if (!includeAltered && a.altered) continue;
    pool[a.slot].push(a);
  }
  for (const slot of ARMOR_SLOTS) {
    const st = EQUIPMENT[slot];
    if (st.locked && st.id) {
      const item = ARMOR_BY_ID.get(st.id);
      pool[slot] = item ? [item] : [];
    }
  }
  return pool;
}

function getRequiredArmorSlots() {
  return ARMOR_SLOTS.filter((slot) => {
    const st = EQUIPMENT[slot];
    if (st.locked && !st.id) return false;
    return true;
  });
}

const DAMAGE_TYPE_LABELS = {
  phy: "Physical (standard)",
  strike: "Strike",
  slash: "Slash",
  pierce: "Pierce",
  magic: "Magic",
  fire: "Fire",
  lightning: "Lightning",
  holy: "Holy",
};

function currentObjective() {
  const goal = document.querySelector('input[name="goal"]:checked').value;
  if (goal === "resistance") {
    return { type: "resistance", stat: document.getElementById("resistance-stat").value };
  }
  if (goal === "damage") {
    return negationObjective(document.getElementById("damage-type").value);
  }
  if (goal === "negation" || goal === "minweight_negation") {
    return { type: "negation" };
  }
  if (goal === "minweight") {
    const metric = document.getElementById("minweight-metric").value;
    if (metric === "negation") return { type: "negation" };
    if (NEGATION_TYPES.includes(metric)) return negationObjective(metric);
    return { type: "poise" };
  }
  return { type: "poise" };
}

function applyArmorResult(result) {
  for (const slot of ARMOR_SLOTS) {
    if (EQUIPMENT[slot].locked) continue;
    const item = result.selection && result.selection[slot];
    EQUIPMENT[slot].id = item ? item.id : null;
  }
  saveEquipment();
  renderEquipment();
}

function lockedHint() {
  const bits = [];
  for (const slot of ALL_SLOTS) {
    if (slotKind(slot) === "talisman" && !isTalismanSlotActive(slot)) continue;
    if (!EQUIPMENT[slot].locked) continue;
    const item = itemForSlot(slot);
    bits.push(item ? `${SLOT_LABELS[slot]}: ${item.name}` : `${SLOT_LABELS[slot]} empty`);
  }
  return bits.length ? ` Locked: ${bits.join("; ")}.` : "";
}

function trackOptimize(ok) {
  const goal = document.querySelector('input[name="goal"]:checked')?.value || "";
  trackEvent("optimize");
  if (goal === "poise" || goal === "negation" || goal === "damage" || goal === "resistance" || goal === "minweight") {
    trackEvent(`optimize-${goal}`);
  }
  if (goal === "damage") {
    trackEvent(`optimize-damage-${document.getElementById("damage-type").value}`);
  } else if (goal === "resistance") {
    trackEvent(`optimize-resistance-${document.getElementById("resistance-stat").value}`);
  } else if (goal === "minweight") {
    trackEvent(`optimize-minweight-${document.getElementById("minweight-metric").value}`);
  }
  trackEvent(ok ? "optimize-ok" : "optimize-fail");
}

function runOptimizer() {
  const goal = document.querySelector('input[name="goal"]:checked').value;
  const pool = getArmorPool();
  const requiredSlots = getRequiredArmorSlots();
  const talismans = getSelectedTalismans();
  const resultsEl = document.getElementById("results-content");
  const hint = lockedHint();

  if (!requiredSlots.length) {
    resultsEl.innerHTML = `<p class="hint">All armor slots are locked empty, so there is nothing for the armor optimizer to fill.${escapeHtml(hint)}</p>`;
    renderSuggestions(resultsEl, currentObjective(), { minWeightMode: goal === "minweight" });
    trackOptimize(false);
    return;
  }

  if (goal === "minweight") {
    const objective = currentObjective();
    const target = parseFloat(document.getElementById("minweight-target").value) || 0;
    const result = minimizeWeightForTarget(pool, objective, target, requiredSlots);
    if (!result) {
      resultsEl.innerHTML = `<p class="hint">No combination reaches that target with the current locks and item pool.${escapeHtml(hint)} Try a lower value, unlock a slot, or check the Item Pool.</p>`;
      trackOptimize(false);
      return;
    }
    applyArmorResult(result);
    renderResult(result, objective, talismans, { minWeightMode: true, target });
    trackOptimize(true);
    return;
  }

  const objective = currentObjective();
  const { result, maxLoad, budgetForArmor } = optimizeArmorForLoad(pool, objective, requiredSlots);
  if (!result) {
    resultsEl.innerHTML = `<p class="hint">No armor combination fits that weight budget with the current locks, weapons, and talismans.${escapeHtml(hint)} Try a lighter load class, unlock a heavy piece, or check the Item Pool.</p>`;
    trackOptimize(false);
    return;
  }
  applyArmorResult(result);
  renderResult(result, objective, talismans, { maxLoad, budgetForArmor });
  trackOptimize(true);
}

function objectiveLabel(objective) {
  if (objective.type === "poise") return "Poise";
  if (objective.type === "negation") {
    if (objective.stat && DAMAGE_TYPE_LABELS[objective.stat]) {
      return `${DAMAGE_TYPE_LABELS[objective.stat]} Negation`;
    }
    return "Total Negation";
  }
  if (objective.type === "resistance") return objective.stat[0].toUpperCase() + objective.stat.slice(1);
  return "Score";
}

function negationResultColumn(objective) {
  const key = (objective.type === "negation" && objective.stat && DAMAGE_TYPES.includes(objective.stat))
    ? objective.stat
    : "phy";
  const short = {
    phy: "Phy",
    strike: "Strike",
    slash: "Slash",
    pierce: "Pierce",
    magic: "Magic",
    fire: "Fire",
    lightning: "Ltng",
    holy: "Holy",
  };
  return { key, header: `${short[key]} Neg` };
}

function renderResult(result, objective, talismans, ctx) {
  const resultsEl = document.getElementById("results-content");
  const armorPieces = ARMOR_SLOTS.map((s) => result.selection[s]).filter(Boolean);
  const weapons = getEquippedWeapons();
  const totalArmorWeight = totalWeight(armorPieces);
  const talismanWeight = totalWeight(talismans);
  const weaponWeight = totalWeight(weapons);
  const totalEquippedWeight = totalArmorWeight + talismanWeight + weaponWeight;

  let html = "";

  if (ctx.minWeightMode) {
    html += `<div class="summary-row">
      <div class="summary-item"><span class="label">Total Weight</span><span class="value">${totalEquippedWeight.toFixed(1)}</span></div>
      <div class="summary-item"><span class="label">${objectiveLabel(objective)}</span><span class="value">${result.totalScore.toFixed(1)}</span></div>
    </div>`;
  } else {
    const ratio = totalEquippedWeight / ctx.maxLoad;
    const cls = loadClass(ratio);
    html += `<div class="summary-row">
      <div class="summary-item"><span class="label">Total Weight</span><span class="value">${totalEquippedWeight.toFixed(1)} / ${ctx.maxLoad.toFixed(1)}</span></div>
      <div class="summary-item"><span class="label">Load</span><span class="value"><span class="badge ${cls}">${(ratio * 100).toFixed(1)}% ${cls}</span></span></div>
      <div class="summary-item"><span class="label">${objectiveLabel(objective)}</span><span class="value">${result.totalScore.toFixed(1)}</span></div>
    </div>`;
  }

  const poise = computeTotalPoise(armorPieces, talismans);
  const neg = computeNegation(armorPieces);
  const res = computeResistances(armorPieces);
  const negTotal = Object.values(neg).reduce((s, v) => s + v, 0);
  const negCol = negationResultColumn(objective);

  html += `<div class="summary-row">
    <div class="summary-item"><span class="label">Poise</span><span class="value">${poise.toFixed(1)}</span></div>
    <div class="summary-item"><span class="label">Total Negation</span><span class="value">${negTotal.toFixed(1)}</span></div>
    <div class="summary-item"><span class="label">Immunity</span><span class="value">${res.immunity}</span></div>
    <div class="summary-item"><span class="label">Robustness</span><span class="value">${res.robustness}</span></div>
    <div class="summary-item"><span class="label">Focus</span><span class="value">${res.focus}</span></div>
    <div class="summary-item"><span class="label">Vitality</span><span class="value">${res.vitality}</span></div>
  </div>`;

  html += `<table class="result-table"><thead><tr>
    <th></th><th>Slot</th><th>Item</th><th>Weight</th><th>Poise</th><th>${escapeHtml(negCol.header)}</th><th>Source</th><th>DLC</th>
  </tr></thead><tbody>`;
  for (const s of ARMOR_SLOTS) {
    const it = result.selection[s];
    if (!it) continue;
    const locked = EQUIPMENT[s].locked ? " (locked)" : "";
    html += `<tr>
      <td>${iconHtml(it, "result-icon")}</td>
      <td>${s}${locked}</td>
      <td>${escapeHtml(armorDisplayName(it))}</td>
      <td>${it.weight}</td>
      <td>${it.resistance.poise}</td>
      <td>${it.negation[negCol.key]}</td>
      <td>${sourceCellHtml(it)}</td>
      <td>${escapeHtml(it.source)}</td>
    </tr>`;
  }
  html += `</tbody></table>`;

  const extras = [];
  if (talismans.length) extras.push(`Talismans: ${talismans.map((t) => t.name).join(", ")}`);
  if (weapons.length) extras.push(`Weapons: ${weapons.map((w) => {
    const slot = WEAPON_SLOTS.find((s) => EQUIPMENT[s].id === w.id);
    return armorDisplayName(w, slot);
  }).join(", ")}`);
  if (extras.length) html += `<p class="hint">${escapeHtml(extras.join(" · "))} — factored into weight / load / poise.</p>`;

  resultsEl.innerHTML = html;
  renderSuggestions(resultsEl, objective, ctx);
}

function scoreTalismanSuggestion(t, objective, preferEquipLoad) {
  const effect = (t.effect || "").toLowerCase();
  let score = 0;
  const el = talismanEquipLoadBonus(t.effect);
  const poise = talismanPoiseBonus(t.effect);
  if (preferEquipLoad && el) score += 200 + el * 200;
  if (objective.type === "poise") {
    if (poise) score += 300 + poise * 200;
    if (effect.includes("poise")) score += 40;
  }
  if (objective.type === "negation") {
    const typeHints = {
      phy: /dragoncrest|physical damage/,
      strike: /strike/,
      slash: /slash/,
      pierce: /pierce/,
      magic: /spelldrake|magic damage|magic negation/,
      fire: /flamedrake|fire damage|fire negation/,
      lightning: /boltdrake|lightning/,
      holy: /haligdrake|holy/,
    };
    if (objective.stat && typeHints[objective.stat]) {
      if (typeHints[objective.stat].test(effect)) score += 90;
      if (objective.stat !== "phy" && /pearldrake|non-physical/.test(effect)) score += 50;
    } else if (/damage negation|physical damage|non-physical|dragoncrest|spelldrake|flamedrake|boltdrake|haligdrake|pearldrake/.test(effect)) {
      score += 80;
    }
  }
  if (objective.type === "resistance") {
    const map = {
      immunity: /immun|poison|rot|scarlet/,
      robustness: /robust|bleed|frost|blood loss/,
      focus: /focus|sleep|madness/,
      vitality: /vitality|death blight|deathblight/,
    };
    const re = map[objective.stat];
    if (re && re.test(effect)) score += 90;
  }
  if (el) score += 15;
  return score;
}

function renderSuggestions(resultsEl, objective, ctx) {
  const stats = getStats();
  const twoHanding = document.getElementById("weapon-two-hand").checked;
  const onlyMeetable = document.getElementById("weapon-only-meetable").checked;
  const rows = [];

  const lockedWeaponIds = new Set();
  for (const s of WEAPON_SLOTS) {
    if (!(EQUIPMENT[s].locked && EQUIPMENT[s].id)) continue;
    const includeAffinities = document.getElementById("include-affinities").checked;
    lockedWeaponIds.add(includeAffinities
      ? `${EQUIPMENT[s].id}:${EQUIPMENT[s].affinity || 0}`
      : EQUIPMENT[s].id);
  }
  const usedWeaponIds = new Set(lockedWeaponIds);
  const weaponPool = WEAPONS.filter((w) => isIncluded(w, "weapons"));
  const ranked = rankWeapons(weaponPool, stats, weaponRankOpts({ twoHanding, onlyMeetable }));
  const includeAffinities = document.getElementById("include-affinities").checked;
  let wi = 0;
  for (const slot of WEAPON_SLOTS) {
    if (EQUIPMENT[slot].locked) continue;
    while (wi < ranked.length && usedWeaponIds.has(weaponSuggestKey(ranked[wi], includeAffinities))) wi += 1;
    if (wi >= ranked.length) break;
    const row = ranked[wi];
    usedWeaponIds.add(weaponSuggestKey(row, includeAffinities));
    wi += 1;
    rows.push({
      slot,
      item: row.weapon,
      kind: "weapon",
      why: "scaling payoff for your stats",
      label: row.label,
      affinity: row.affinity,
      upgrade: row.upgrade,
    });
  }

  const preferEquipLoad = !!(ctx && ctx.minWeightMode) || getLoadBudget().budgetForArmor < 20;
  const lockedTalIds = new Set(
    activeTalismanSlots().filter((s) => EQUIPMENT[s].locked && EQUIPMENT[s].id).map((s) => EQUIPMENT[s].id)
  );
  const usedTalIds = new Set(lockedTalIds);
  const talPool = TALISMANS.filter((t) => isIncluded(t, "talismans") && !usedTalIds.has(t.id));
  const scored = talPool
    .map((t) => ({ t, score: scoreTalismanSuggestion(t, objective, preferEquipLoad) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score);
  let ti = 0;
  for (const slot of activeTalismanSlots()) {
    if (EQUIPMENT[slot].locked) continue;
    while (ti < scored.length && usedTalIds.has(scored[ti].t.id)) ti += 1;
    if (ti >= scored.length) break;
    const t = scored[ti].t;
    usedTalIds.add(t.id);
    ti += 1;
    rows.push({ slot, item: t, kind: "talisman", why: "heuristic for the current goal — not a scored optimum" });
  }

  if (!rows.length) return;

  const wrap = document.createElement("div");
  wrap.className = "suggestions";
  wrap.id = "optimizer-suggestions";
  wrap.innerHTML = `<h3>Suggestions</h3>
    <p class="hint">These are not applied automatically. Click Apply to equip a suggestion onto an unlocked slot, then lock it if you want Optimize to keep it.</p>
    <div class="suggestion-list"></div>`;
  const list = wrap.querySelector(".suggestion-list");
  for (const row of rows) {
    const div = document.createElement("div");
    div.className = "suggestion-row";
    div.dataset.suggestSlot = row.slot;
    div.innerHTML = `${iconHtml(row.item)}
      <div class="sug-body">
        <div class="sug-slot">${escapeHtml(SLOT_LABELS[row.slot])}</div>
        <div>${escapeHtml(row.label || row.item.name)}${sourceTagHtml(row.item.source)} <span class="hint">(${row.item.weight} wt)</span></div>
        <div class="hint">${escapeHtml(row.why)}</div>
      </div>
      <button type="button" class="preset-btn" data-apply-slot="${row.slot}" data-apply-id="${escapeHtml(row.item.id)}" data-apply-affinity="${row.affinity || 0}" data-apply-upgrade="${row.upgrade || 0}">Apply</button>`;
    list.appendChild(div);
  }
  list.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-apply-slot]");
    if (!btn) return;
    const slot = btn.getAttribute("data-apply-slot");
    const id = btn.getAttribute("data-apply-id");
    const affinity = Number(btn.getAttribute("data-apply-affinity") || 0);
    const upgrade = Number(btn.getAttribute("data-apply-upgrade") || 0);
    if (slotKind(slot) === "talisman") {
      if (!isTalismanSlotActive(slot)) return;
      if (EQUIPMENT[slot].locked) return;
    }
    if (EQUIPMENT[slot].locked) return;
    setSlotItem(slot, id, slotKind(slot) === "weapon" ? { affinity, upgrade } : undefined);
  });
  resultsEl.appendChild(wrap);
}

function populateWeaponCategories() {
  const categories = [...new Set(WEAPONS.map((w) => w.category).filter(Boolean))].sort();
  for (const selectId of ["weapon-category", "pool-weapon-category"]) {
    const select = document.getElementById(selectId);
    if (!select) continue;
    for (const c of categories) {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      select.appendChild(opt);
    }
  }
}

function renderWeaponResults() {
  const stats = getStats();
  const twoHanding = document.getElementById("weapon-two-hand").checked;
  const onlyMeetable = document.getElementById("weapon-only-meetable").checked;
  const category = document.getElementById("weapon-category").value || null;

  const pool = WEAPONS.filter((w) => isIncluded(w, "weapons"));
  const ranked = rankWeapons(pool, stats, weaponRankOpts({ twoHanding, onlyMeetable, category })).slice(0, 25);

  let html = `<table class="result-table"><thead><tr>
    <th></th><th>Weapon</th><th>Type</th><th>Scaling (Str/Dex/Int/Fai/Arc)</th><th>Ref. Phy AR</th><th>Weight</th><th>Source</th><th>DLC</th>
  </tr></thead><tbody>`;
  for (const r of ranked) {
    const w = r.weapon;
    const sc = r.scaling || w.scaling || {};
    html += `<tr>
      <td>${iconHtml(w, "result-icon")}</td>
      <td>${escapeHtml(r.label || w.name)}</td>
      <td>${escapeHtml(w.category)}</td>
      <td>${sc.str || "-"}/${sc.dex || "-"}/${sc.int || "-"}/${sc.fai || "-"}/${sc.arc || "-"}</td>
      <td>${w.attack.phy ?? "-"}</td>
      <td>${w.weight}</td>
      <td>${sourceCellHtml(w)}</td>
      <td>${escapeHtml(w.source)}</td>
    </tr>`;
  }
  html += `</tbody></table>`;
  document.getElementById("weapon-results").innerHTML = html;
}

function poolItemsForType(type) {
  if (type === "armor") return ARMOR;
  if (type === "weapons") return WEAPONS;
  return TALISMANS;
}

function poolVisibleItems() {
  const type = poolActiveTab;
  let items = poolItemsForType(type);

  if (type === "armor") {
    const slot = document.getElementById("pool-armor-slot").value;
    items = items.filter((a) => a.slot === slot);
  } else if (type === "weapons") {
    const category = document.getElementById("pool-weapon-category").value;
    if (category) items = items.filter((w) => w.category === category);
  }

  const q = (document.getElementById("pool-search").value || "").toLowerCase();
  if (q) items = items.filter((it) => it.name.toLowerCase().includes(q));

  return items;
}

function renderPoolChecklist() {
  const type = poolActiveTab;
  const container = document.getElementById("pool-checklist");
  const items = poolVisibleItems();

  container.innerHTML = "";
  for (const it of items) {
    const inPool = !EXCLUDED[type].has(it.id);
    const row = document.createElement("label");
    row.className = "pick-item pool-checklist-item" + (inPool ? "" : " excluded");
    const areaHint = (it.areas && it.areas.length) ? ` <span class="hint">(${it.areas.join(", ")})</span>` : "";
    row.innerHTML = `<span><input type="checkbox" ${inPool ? "checked" : ""}> ${escapeHtml(armorDisplayName(it))}${sourceTagHtml(it.source)}${areaHint}</span>`;
    const checkbox = row.querySelector("input");
    checkbox.addEventListener("change", () => {
      setPoolItemIncluded(type, it, checkbox.checked);
      row.classList.toggle("excluded", !checkbox.checked);
      updatePoolCountLabel();
      renderAreaFilters();
      onExclusionsChanged(type);
    });
    container.appendChild(row);
  }

  updatePoolCountLabel();
  renderAreaFilters();
}

function renderAreaFilters() {
  const container = document.getElementById("pool-area-filters");
  if (!container) return;

  container.innerHTML = "";

  const label = document.createElement("div");
  label.className = "hint area-filters-label";
  label.textContent = "Region chips quickly check or uncheck items you can obtain there. They do not lock the list — use the checkboxes (or Check all / Uncheck all) to include or exclude anything. None, then Limgrave, for a Limgrave-only run. Starting Gear is class kits; pick your class next to All / None to start from that kit.";
  container.appendChild(label);

  const actions = document.createElement("div");
  actions.className = "area-filters-row area-filter-actions";
  const allBtn = document.createElement("button");
  allBtn.id = "area-select-all";
  allBtn.type = "button";
  allBtn.className = "preset-btn" + (allPoolItemsIncluded() ? " area-all-on" : "");
  allBtn.textContent = "All";
  allBtn.addEventListener("click", () => {
    selectAllRegions();
    includeAllPoolItems();
    onPoolExclusionsChanged();
  });
  const noneBtn = document.createElement("button");
  noneBtn.id = "area-select-none";
  noneBtn.type = "button";
  noneBtn.className = "preset-btn";
  noneBtn.textContent = "None";
  noneBtn.addEventListener("click", () => {
    selectNoRegions();
    onPoolExclusionsChanged();
  });
  actions.appendChild(allBtn);
  actions.appendChild(noneBtn);

  const classWrap = document.createElement("label");
  classWrap.className = "starting-class-picker";
  classWrap.setAttribute("for", "starting-class");
  classWrap.append("Class ");
  const classSelect = document.createElement("select");
  classSelect.id = "starting-class";
  const anyOpt = document.createElement("option");
  anyOpt.value = "";
  anyOpt.textContent = "Any class";
  classSelect.appendChild(anyOpt);
  for (const cls of STARTING_CLASS_ORDER) {
    const opt = document.createElement("option");
    opt.value = cls;
    opt.textContent = cls;
    classSelect.appendChild(opt);
  }
  classSelect.value = selectedStartingClass;
  classSelect.addEventListener("change", () => {
    selectedStartingClass = classSelect.value;
    if (selectedStartingClass) selectedRegions.add(STARTING_GEAR_REGION);
    onPoolExclusionsChanged();
  });
  classWrap.appendChild(classSelect);
  actions.appendChild(classWrap);
  container.appendChild(actions);

  const row = document.createElement("div");
  row.className = "area-filters-row";
  for (const region of MASTER_REGION_ORDER) {
    const items = itemsInRegion(region);
    const on = selectedRegions.has(region);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "area-btn" + (on ? " area-btn-on" : " area-btn-off")
      + (DLC_REGIONS.has(region) ? " area-btn-dlc" : "")
      + (META_REGIONS.has(region) ? " area-btn-meta" : "");
    btn.textContent = region;
    btn.title = on
      ? `${items.length} item(s) obtainable here. Click to uncheck them (you can still check any item by hand).`
      : `${items.length} item(s) obtainable here. Click to check them.`;
    btn.addEventListener("click", () => toggleAreaFilter(region));
    row.appendChild(btn);
  }
  container.appendChild(row);
}

function toggleAreaFilter(region) {
  if (selectedRegions.has(region)) selectedRegions.delete(region);
  else selectedRegions.add(region);
  onPoolExclusionsChanged();
}

function onPoolExclusionsChanged() {
  applyRegionExclusions();
  renderPoolChecklist();
  onExclusionsChanged(poolActiveTab);
  saveState();
}

function updatePoolCountLabel() {
  const type = poolActiveTab;
  const items = poolVisibleItems();
  const includedCount = items.filter((it) => isIncluded(it, type)).length;
  document.getElementById("pool-count-label").textContent = `${includedCount} / ${items.length} shown items included`;
}

function onExclusionsChanged(type) {
  if (type === "weapons" || type === "armor" || type === "talismans") {
    renderWeaponResults();
  }
  if (pickerSlot) renderPickerList();
}

function setPoolTab(tab) {
  poolActiveTab = tab;
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tab);
  });
  document.querySelectorAll(".pool-tab").forEach((el) => {
    el.classList.toggle("hidden", el.id !== `pool-tab-${tab}`);
  });
  document.getElementById("pool-search").value = "";
  renderPoolChecklist();
}

function setupSaveImport() {
  const btn = document.getElementById("load-save-btn");
  const input = document.getElementById("save-file-input");
  const overlay = document.getElementById("save-character-overlay");
  const cancel = document.getElementById("save-character-cancel");
  const confirm = document.getElementById("save-import-confirm");
  const copyPath = document.getElementById("copy-save-path-btn");
  if (!btn || !input || !overlay) return;

  btn.addEventListener("click", () => {
    trackEvent("save-open");
    input.value = "";
    input.click();
  });
  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (file) loadSaveFile(file);
  });
  cancel.addEventListener("click", closeSaveCharacterPicker);
  confirm.addEventListener("click", confirmSaveImport);
  overlay.addEventListener("click", (e) => {
    if (e.target.id === "save-character-overlay") closeSaveCharacterPicker();
  });
  if (copyPath) {
    copyPath.addEventListener("click", copySaveImportPath);
  }
}

async function copySaveImportPath() {
  const pathEl = document.getElementById("save-import-path");
  const btn = document.getElementById("copy-save-path-btn");
  const text = pathEl ? pathEl.textContent.trim() : "%APPDATA%\\EldenRing";
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  if (!btn) return;
  const prev = btn.textContent;
  btn.textContent = "Copied";
  setTimeout(() => { btn.textContent = prev; }, 1500);
}

let pendingSaveCharacters = [];
let selectedSaveCharacterIndex = 0;

function setSaveImportStatus(message, kind) {
  const el = document.getElementById("save-import-status");
  if (!el) return;
  el.textContent = message || "";
  el.classList.remove("save-import-ok", "save-import-err");
  if (kind) el.classList.add(kind);
}

function closeSaveCharacterPicker() {
  const overlay = document.getElementById("save-character-overlay");
  if (overlay) overlay.classList.add("hidden");
  pendingSaveCharacters = [];
}

function openSaveCharacterPicker(characters) {
  pendingSaveCharacters = characters;
  selectedSaveCharacterIndex = 0;
  renderSaveCharacterList();
  document.getElementById("save-import-inventory").checked = true;
  document.getElementById("save-import-chest").checked = true;
  document.getElementById("save-import-stats").checked = true;
  document.getElementById("save-import-equipped").checked = true;
  document.getElementById("save-character-overlay").classList.remove("hidden");
}

function renderSaveCharacterList() {
  const list = document.getElementById("save-character-list");
  list.innerHTML = "";
  pendingSaveCharacters.forEach((ch, i) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "pick-item save-character-row" + (i === selectedSaveCharacterIndex ? " selected" : "");
    const extra = ch.playtime ? ` · ${ch.playtime}` : "";
    row.innerHTML = `<span>${escapeHtml(ch.name)}</span><span class="hint">RL ${ch.level}${extra}</span>`;
    row.addEventListener("click", () => {
      selectedSaveCharacterIndex = i;
      renderSaveCharacterList();
    });
    list.appendChild(row);
  });
}

async function loadSaveFile(file) {
  setSaveImportStatus("Reading save…");
  try {
    const buf = await file.arrayBuffer();
    const parsed = ER_SAVE.parseSave(buf);
    setSaveImportStatus(`Loaded ${parsed.characters.length} character${parsed.characters.length === 1 ? "" : "s"} — choose what to import.`);
    trackEvent("save-parsed");
    openSaveCharacterPicker(parsed.characters);
  } catch (err) {
    trackEvent("save-parse-error");
    setSaveImportStatus(err.message || "Could not read that save", "save-import-err");
  }
}

function confirmSaveImport() {
  const character = pendingSaveCharacters[selectedSaveCharacterIndex];
  if (!character) return;
  const wantInventory = document.getElementById("save-import-inventory").checked;
  const wantChest = document.getElementById("save-import-chest").checked;
  const wantStats = document.getElementById("save-import-stats").checked;
  const wantEquipped = document.getElementById("save-import-equipped").checked;
  if (!wantInventory && !wantChest && !wantStats && !wantEquipped) {
    setSaveImportStatus("Choose at least one thing to import.", "save-import-err");
    return;
  }
  applySaveCharacter(character, {
    inventory: wantInventory,
    chest: wantChest,
    stats: wantStats,
    equipped: wantEquipped,
  });
  trackEvent("save-import");
  closeSaveCharacterPicker();
}

function applySaveStats(stats) {
  if (!stats) return;
  for (const [key, id] of Object.entries(STAT_INPUT_IDS)) {
    const v = clampInt(stats[key], 1, 99);
    if (v != null) document.getElementById(id).value = String(v);
  }
  if (stats.talismanSlotCount) {
    const n = Math.max(1, Math.min(4, stats.talismanSlotCount));
    talismanSlotCount = n;
    const sel = document.getElementById("talisman-slot-count");
    if (sel) sel.value = String(n);
  }
  saveState();
  renderEquipment();
  updateDerivedCharacterInfo();
  renderWeaponResults();
}

function itemFitsImportedSlot(slot, id) {
  if (!id) return true;
  const kind = slotKind(slot);
  if (kind === "armor") {
    const it = ARMOR_BY_ID.get(id);
    return !!(it && it.slot === slot);
  }
  if (kind === "weapon") return WEAPONS_BY_ID.has(id);
  return TALISMANS_BY_ID.has(id);
}

function applySaveEquipped(equipped) {
  const { slots, filled, skipped } = ER_SAVE.mapEquipped(equipped, GAME_IDS);
  let neededPouches = talismanSlotCount;
  TALISMAN_SLOTS.forEach((slot, i) => {
    if (slots[slot]) neededPouches = Math.max(neededPouches, i + 1);
  });
  if (neededPouches !== talismanSlotCount) {
    talismanSlotCount = Math.max(1, Math.min(4, neededPouches));
    const sel = document.getElementById("talisman-slot-count");
    if (sel) sel.value = String(talismanSlotCount);
  }

  let applied = 0;
  let lockedSkip = 0;
  for (const slot of ALL_SLOTS) {
    if (!(slot in slots)) continue;
    if (EQUIPMENT[slot].locked) {
      lockedSkip++;
      continue;
    }
    const rec = slots[slot];
    const id = rec && rec.id && itemFitsImportedSlot(slot, rec.id) ? rec.id : null;
    EQUIPMENT[slot].id = id;
    EQUIPMENT[slot].affinity = (id && rec && rec.affinity) || 0;
    EQUIPMENT[slot].upgrade = (id && rec && rec.upgrade) || 0;
    if (id) applied++;
  }
  saveState();
  renderEquipment();
  updateDerivedCharacterInfo();
  renderWeaponResults();
  return { applied, filled, skipped, lockedSkip };
}

function applySaveCharacter(character, opts) {
  if (character.gender === "female" || character.gender === "male") {
    setCharacterGender(character.gender);
  }
  const parts = [];
  if (opts.inventory || opts.chest) {
    const bags = [];
    if (opts.inventory) bags.push(character.inventory);
    if (opts.chest) bags.push(character.chest);
    const raw = ER_SAVE.mergeOwnedBags(...bags);
    const { owned, matched, skipped, instances } = ER_SAVE.mapOwned(raw, GAME_IDS);
    applyOwnedFromSave(owned, instances);
    const extra = skipped ? `, skipped ${skipped} unknown` : "";
    parts.push(`${matched} known items${extra}`);
    const drawer = document.getElementById("item-pool-drawer");
    const toggleBtn = document.getElementById("toggle-item-pool-drawer");
    if (drawer && drawer.classList.contains("hidden")) {
      drawer.classList.remove("hidden");
      if (toggleBtn) {
        toggleBtn.setAttribute("aria-expanded", "true");
        toggleBtn.textContent = "Customize Item Pool ▴";
      }
    }
    renderPoolChecklist();
  }
  if (opts.stats) {
    applySaveStats(character.stats);
    parts.push(`RL ${character.level} stats`);
  }
  if (opts.equipped) {
    const result = applySaveEquipped(character.equipped);
    const extra = result.lockedSkip ? `, left ${result.lockedSkip} locked` : "";
    parts.push(`${result.applied} equipped items${extra}`);
  }
  setSaveImportStatus(`Imported ${character.name}: ${parts.join("; ")}.`, "save-import-ok");
}

function applyOwnedFromSave(owned, instances) {
  OWNED_WEAPON_INSTANCES = instances || {};
  for (const type of ["armor", "weapons", "talismans"]) {
    const ids = owned[type] || new Set();
    for (const it of poolItemsForType(type)) {
      setPoolItemIncluded(type, it, ids.has(it.id));
    }
  }
  onExclusionsChanged(poolActiveTab);
  saveState();
}

function setupItemPoolDrawer() {
  const toggleBtn = document.getElementById("toggle-item-pool-drawer");
  const drawer = document.getElementById("item-pool-drawer");

  toggleBtn.addEventListener("click", () => {
    const isHidden = drawer.classList.toggle("hidden");
    toggleBtn.setAttribute("aria-expanded", String(!isHidden));
    toggleBtn.textContent = isHidden ? "Customize Item Pool ▾" : "Customize Item Pool ▴";
    if (!isHidden) {
      renderPoolChecklist();
      trackEvent("pool-open");
    }
  });

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => setPoolTab(btn.getAttribute("data-tab")));
  });

  document.getElementById("pool-armor-slot").addEventListener("change", renderPoolChecklist);
  document.getElementById("pool-weapon-category").addEventListener("change", renderPoolChecklist);
  document.getElementById("pool-search").addEventListener("input", renderPoolChecklist);

  document.getElementById("pool-select-all").addEventListener("click", () => {
    const type = poolActiveTab;
    for (const it of poolVisibleItems()) setPoolItemIncluded(type, it, true);
    renderPoolChecklist();
    onExclusionsChanged(type);
  });

  document.getElementById("pool-select-none").addEventListener("click", () => {
    const type = poolActiveTab;
    for (const it of poolVisibleItems()) setPoolItemIncluded(type, it, false);
    renderPoolChecklist();
    onExclusionsChanged(type);
  });

  document.getElementById("pool-reset").addEventListener("click", () => {
    selectAllRegions();
    includeAllPoolItems();
    onPoolExclusionsChanged();
  });

  ["source-elden-ring", "source-shadow-of-the-erdtree", "source-tarnished-edition"].forEach((id) => {
    document.getElementById(id).addEventListener("change", () => {
      saveState();
      renderWeaponResults();
      renderPoolChecklist();
      if (pickerSlot) renderPickerList();
    });
  });

  applyRegionExclusions();
  renderAreaFilters();
}

function setupGoalToggles() {
  const radios = document.querySelectorAll('input[name="goal"]');
  radios.forEach((r) => r.addEventListener("change", () => {
    updateGoalVisibility();
    saveState();
  }));
  ["resistance-stat", "damage-type", "minweight-metric", "minweight-target"].forEach((id) => {
    document.getElementById(id).addEventListener("change", saveState);
    document.getElementById(id).addEventListener("input", saveState);
  });
  updateGoalVisibility();
}

function updateGoalVisibility() {
  const goal = document.querySelector('input[name="goal"]:checked').value;
  document.getElementById("goal-resistance-options").classList.toggle("hidden", goal !== "resistance");
  document.getElementById("goal-damage-options").classList.toggle("hidden", goal !== "damage");
  document.getElementById("goal-minweight-options").classList.toggle("hidden", goal !== "minweight");
  document.getElementById("load-budget-section").classList.toggle("hidden", goal === "minweight");
}

async function init() {
  await loadData();
  loadSavedState();
  populateWeaponCategories();
  applySavedWeaponCategory(readSave());
  setupEquipmentBoard();
  setupGoalToggles();
  setupItemPoolDrawer();
  setupSaveImport();
  renderEquipment();
  updateDerivedCharacterInfo();

  document.querySelectorAll("#panel-character input")
    .forEach((el) => el.addEventListener("input", () => {
      saveState();
      updateDerivedCharacterInfo();
      renderWeaponResults();
    }));
  document.getElementById("character-gender").addEventListener("change", (e) => {
    setCharacterGender(e.target.value);
  });

  document.getElementById("load-ratio").addEventListener("input", (e) => {
    applyLoadRatio(ratioFromSliderUnits(e.target.value));
    updateLoadBudgetDisplay();
    saveState();
  });

  const LOAD_PRESET_EVENTS = { "0.299": "load-light", "0.699": "load-medium", "0.999": "load-heavy" };
  document.querySelectorAll(".preset-btn[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const preset = btn.getAttribute("data-preset");
      applyLoadRatio(preset);
      updateLoadBudgetDisplay();
      saveState();
      const eventName = LOAD_PRESET_EVENTS[preset];
      if (eventName) trackEvent(eventName);
    });
  });

  document.getElementById("optimize-btn").addEventListener("click", runOptimizer);

  ["weapon-two-hand", "weapon-only-meetable", "weapon-category"].forEach((id) => {
    document.getElementById(id).addEventListener("change", () => {
      saveState();
      renderWeaponResults();
    });
  });

  renderWeaponResults();
}

document.addEventListener("DOMContentLoaded", init);
