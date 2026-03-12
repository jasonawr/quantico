const modelBody = document.getElementById("modelTableBody");
const familyList = document.getElementById("familyList");

async function loadStrategies() {
  const res = await fetch("/api/strategies");
  const data = await res.json();
  modelBody.innerHTML = data
    .map((x) => `<tr><td>${x.key}</td><td>${x.name}</td><td>${x.complexity}</td><td>${x.description}</td></tr>`)
    .join("");
}

async function loadCatalog() {
  const res = await fetch("/api/strategies/catalog");
  const data = await res.json();
  const families = data.families || [];
  familyList.innerHTML = families
    .map(
      (f) => `
      <div class="panel" style="margin-bottom:10px;">
        <div style="font-weight:700; margin-bottom:6px;">${f.name}</div>
        <div style="color:#8ca0d6; margin-bottom:6px;">Strategies: ${(f.strategies || []).join(", ")}</div>
        <div style="font-size:0.85rem;">Refs: ${(f.references || []).join(" | ")}</div>
      </div>
    `,
    )
    .join("");
}

(async () => {
  await loadStrategies();
  await loadCatalog();
})();
