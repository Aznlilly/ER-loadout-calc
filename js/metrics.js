// Privacy-friendly GoatCounter events. Never send character names, save
// contents, item ids, or exact stats — only allowlisted event names.
// Paths are scoped under /project/er-tools/ so this site is distinct on the
// shared in-a.elsewhere.moe instance.
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
    "github-issue",
  ]);

  const pending = [];
  let waiting = false;

  function project() {
    return typeof GOATCOUNTER_PROJECT === "string" && GOATCOUNTER_PROJECT
      ? GOATCOUNTER_PROJECT
      : "er-tools";
  }

  function eventPath(eventName) {
    return `/project/${project()}/event/${eventName}`;
  }

  function eventTitle(title) {
    return `${project()}: ${title}`;
  }

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

  function trackEvent(eventName, title) {
    if (!ALLOWED.has(eventName)) return;
    pending.push({
      path: eventPath(eventName),
      title: eventTitle(title || eventName),
      event: true,
    });
    waitForGoat();
  }

  return { trackEvent, ALLOWED };
})();

function trackEvent(eventName, title) {
  ER_METRICS.trackEvent(eventName, title);
}

document.addEventListener("DOMContentLoaded", () => {
  const link = document.getElementById("github-issue-link");
  if (link) link.addEventListener("click", () => trackEvent("github-issue"));
});
