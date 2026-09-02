/**
 * Bitemporal Timeline and Event Log View
 */
export class TimelineView {
  constructor(containerId, state, onAction) {
    this.container = document.getElementById(containerId);
    this.state = state;
    this.onAction = onAction;
    this.events = [];
    this.searchQuery = "";
    this.roleFilter = "";

    document.getElementById("timeline-search")?.addEventListener("input", (e) => {
      this.searchQuery = e.target.value.toLowerCase();
      this.render();
    });

    document.getElementById("timeline-role-filter")?.addEventListener("change", (e) => {
      this.roleFilter = e.target.value;
      this.fetchEvents();
    });

    document.getElementById("btn-refresh-timeline")?.addEventListener("click", () => {
      this.fetchEvents();
    });
  }

  async fetchEvents() {
    try {
      const url = `/api/timeline?ramo=${this.state.currentBranch}&papel=${this.roleFilter}`;
      const res = await fetch(url);
      const data = await res.json();
      this.events = data.eventos || [];
      this.render();
    } catch (err) {
      console.error("Erro ao carregar timeline:", err);
    }
  }

  render() {
    this.container.innerHTML = "";
    const filtered = this.events.filter((e) => {
      if (!this.searchQuery) return true;
      const text = `${e.seq} ${e.tipo} ${e.autor} ${JSON.stringify(e.payload)}`.toLowerCase();
      return text.includes(this.searchQuery);
    });

    if (filtered.length === 0) {
      this.container.innerHTML = `<div style="font-size:11px; color:var(--text-faint); padding:10px;">Nenhum evento registrado no log.</div>`;
      return;
    }

    for (const ev of filtered.slice().reverse()) {
      const card = document.createElement("div");
      card.className = "timeline-event-card";
      card.innerHTML = `
        <div>
          <span style="font-family:var(--font-mono); color:var(--accent-cyan); font-weight:600;">#${ev.seq}</span>
          <strong style="margin-left:6px;">${ev.tipo}</strong>
          <span style="color:var(--text-muted); margin-left:6px;">por <em>${ev.autor}</em> (${ev.papel})</span>
        </div>
        <div style="font-size:10px; color:var(--text-faint); display:flex; align-items:center; gap:8px;">
          <span>${ev.timestamp.slice(11, 19)}</span>
          <button class="btn btn-xs btn-secondary btn-jump-version" data-version="${ev.seq}">Replay até aqui</button>
        </div>
      `;

      card.querySelector(".btn-jump-version")?.addEventListener("click", (e) => {
        e.stopPropagation();
        this.onAction("TIME_TRAVEL_TO", { version: ev.seq });
      });

      this.container.appendChild(card);
    }
  }
}
