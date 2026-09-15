// Privacy-friendly GoatCounter events. Never send character names, save
// contents, item ids, or exact stats — only allowlisted event names.
const ER_METRICS = (() => {
  const DAMAGE = ["phy", "strike", "slash", "pierce", "magic", "fire", "lightning", "holy"];
  const RESISTS = ["immunity", "robustness", "focus", "vitality"];
  const MINWEIGHT = ["poise", "negation", ...DAMAGE];

  const ALLOWED = new Set([
    "optimize",
    "optimize-poise",
    "optimize-negation",
    "optimize-damage",
    "optimize-resistance",
    "optimize-minweight",
    ...DAMAGE.map((t) => `optimize-damage-${t}`),
    ...RESISTS.map((t) => `optimize-resistance-${t}`),
    ...MINWEIGHT.map((t) => `optimize-minweight-${t}`),
    "optimize-ok",
    "optimize-fail",
    "save-open",
    "save-parsed",
    "save-parse-error",
    "save-import",
    "reset",
    "unequip-all",
    "load-light",
    "load-medium",
    "load-heavy",
    "pool-open",
  ]);

  const pending = [];
  let waiting = false;

  function flush() {
    const gc = window.goatcounter;
    if (!gc || typeof gc.count !== "function") return false;
    while (pending.length) gc.count(pending.shift());
    return true;
  }

  function waitForGoat() {
    if (flush() || waiting) return;
    waiting = true;
    let n = 0;
    const t = setInterval(() => {
      n += 1;
      if (flush() || n > 50) {
        clearInterval(t);
        waiting = false;
      }
    }, 200);
  }

  function trackUsage(name) {
    if (!ALLOWED.has(name)) return;
    const vars = { path: name, title: name, event: true, no_session: true };
    pending.push(vars);
    waitForGoat();
  }

  return { trackUsage, ALLOWED };
})();

function trackUsage(name) {
  ER_METRICS.trackUsage(name);
}
