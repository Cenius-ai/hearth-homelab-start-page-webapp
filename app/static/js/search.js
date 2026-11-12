/** Client-side quick search over the rendered grid and bookmark row.

Nothing is fetched: the catalog is already in the DOM, so filtering is instant
and works with the network down.
*/

export function initSearch({ input, emptyState, termTarget, clearButtons = [] }) {
  const noServices = document.getElementById("no-services");

  function setNoServices() {
    if (!noServices) return;
    const total = document.querySelectorAll("#tile-grid .tile").length;
    noServices.hidden = total > 0;
  }

  function apply() {
    const query = input ? input.value.trim().toLowerCase() : "";
    let visible = 0;

    document.querySelectorAll("#tile-grid .group").forEach((group) => {
      let groupVisible = 0;
      group.querySelectorAll(".tile").forEach((tile) => {
        const match = !query || (tile.dataset.search || "").includes(query);
        tile.hidden = !match;
        if (match) groupVisible += 1;
      });
      group.hidden = groupVisible === 0;
      const count = group.querySelector("[data-count]");
      if (count) count.textContent = String(groupVisible);
      visible += groupVisible;
    });

    document.querySelectorAll(".chip").forEach((chip) => {
      const match = !query || (chip.dataset.search || "").includes(query);
      chip.hidden = !match;
    });

    if (emptyState) {
      const showEmpty = Boolean(query) && visible === 0;
      emptyState.hidden = !showEmpty;
      if (showEmpty && termTarget) termTarget.textContent = input.value.trim();
    }

    clearButtons.forEach((button) => {
      if (button) button.hidden = !query;
    });

    setNoServices();
  }

  function clear() {
    if (!input) return;
    input.value = "";
    apply();
    input.focus();
  }

  if (input) {
    input.addEventListener("input", apply);

    document.addEventListener("keydown", (event) => {
      const target = event.target;
      const tag = target && target.tagName ? target.tagName.toLowerCase() : "";
      const typing =
        tag === "input" || tag === "textarea" || tag === "select" || (target && target.isContentEditable);

      if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        input.focus();
        input.select();
        return;
      }

      if (event.key === "Escape" && (document.activeElement === input || input.value)) {
        if (input.value) {
          input.value = "";
          apply();
        }
        if (document.activeElement === input) input.blur();
      }
    });
  }

  clearButtons.forEach((button) => {
    if (button) button.addEventListener("click", clear);
  });

  apply();

  return { refresh: apply, clear };
}
