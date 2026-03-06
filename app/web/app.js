const STORAGE_KEYS = {
  apiUrl: "adamhub.apiUrl",
  apiKey: "adamhub.apiKey",
};

const PAGES = [
  { id: "dashboard", label: "Dashboard", subtitle: "Overview globale" },
  { id: "tasks", label: "Tasks", subtitle: "Pilotage des taches" },
  { id: "finances", label: "Finances", subtitle: "Transactions et budget" },
  { id: "groceries", label: "Groceries", subtitle: "Liste de courses" },
  { id: "recipes", label: "Recipes", subtitle: "Recettes et ingredients" },
  { id: "meal-plans", label: "Meal Plans", subtitle: "Planning repas auto courses" },
  { id: "habits", label: "Habits", subtitle: "Routines quotidiennes" },
  { id: "goals", label: "Goals", subtitle: "Objectifs et jalons" },
  { id: "events", label: "Events", subtitle: "Agenda et planning" },
  { id: "calendar", label: "Calendar", subtitle: "Vue unifiee (tasks, repas, abonnements...)" },
  { id: "subscriptions", label: "Subscriptions", subtitle: "Abonnements recurrents" },
  { id: "pantry", label: "Pantry", subtitle: "Inventaire maison" },
  { id: "notes", label: "Notes", subtitle: "Journal et idees" },
  { id: "linear", label: "Linear", subtitle: "Projets et tickets synchronises" },
  { id: "ai", label: "AI Console", subtitle: "Executer des actions skill" },
];

const state = {
  activePage: "dashboard",
  dashboardMonthStart: null,
  dashboardSelectedDay: null,
};

const el = {
  nav: document.getElementById("nav"),
  pageTitle: document.getElementById("pageTitle"),
  pageSubtitle: document.getElementById("pageSubtitle"),
  refreshAllBtn: document.getElementById("refreshAllBtn"),
  apiUrl: document.getElementById("apiUrl"),
  apiKey: document.getElementById("apiKey"),
  saveConfigBtn: document.getElementById("saveConfigBtn"),
  testConfigBtn: document.getElementById("testConfigBtn"),
  sections: Object.fromEntries(PAGES.map((p) => [p.id, document.getElementById(`section-${p.id}`)])),
};

function showToast(message, isError = false) {
  let toast = document.querySelector(".toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.background = isError ? "#8d1f17" : "#121619";
  toast.classList.add("show");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => toast.classList.remove("show"), 2300);
}

function getConfig() {
  const fallback = window.location.origin;
  const storedUrl = localStorage.getItem(STORAGE_KEYS.apiUrl);
  const storedKey = localStorage.getItem(STORAGE_KEYS.apiKey);
  const uiUrl = el.apiUrl?.value || "";
  const uiKey = el.apiKey?.value || "";
  const apiUrl = normalizeApiUrl(storedUrl || uiUrl || fallback);
  const apiKey = normalizeApiKey(storedKey || uiKey || "");
  return { apiUrl, apiKey };
}

function saveConfig() {
  localStorage.setItem(STORAGE_KEYS.apiUrl, normalizeApiUrl(el.apiUrl.value));
  localStorage.setItem(STORAGE_KEYS.apiKey, normalizeApiKey(el.apiKey.value));
  showToast("Configuration sauvegardee");
}

function normalizeApiUrl(value) {
  let out = String(value || "").trim();
  out = out.replace(/\/+$/, "");
  if (out.endsWith("/api/v1")) out = out.slice(0, -7);
  return out;
}

function normalizeApiKey(value) {
  let out = String(value || "").trim();
  if ((out.startsWith("\"") && out.endsWith("\"")) || (out.startsWith("'") && out.endsWith("'"))) {
    out = out.slice(1, -1).trim();
  }
  return out;
}

async function testConnection() {
  saveConfig();
  try {
    await api("/api/v1/auth/check");
    showToast("Connexion API OK");
  } catch (err) {
    const message = String(err.message || err);
    if (message.toLowerCase().includes("not found")) {
      showToast("API URL invalide. Mets la racine (ex: http://localhost:8000), sans /api/v1.", true);
      return;
    }
    if (message.toLowerCase().includes("invalid api key")) {
      showToast("API key invalide. Mets la bonne cle dans la config.", true);
      return;
    }
    showToast(`Connexion impossible: ${message}`, true);
  }
}

function joinUrl(base, path) {
  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  return `${normalizedBase}${path}`;
}

async function api(path, options = {}) {
  const { apiUrl, apiKey } = getConfig();
  const headers = {
    ...(options.headers || {}),
    "Content-Type": "application/json",
  };
  if (apiKey) headers["X-API-Key"] = apiKey;

  const response = await fetch(joinUrl(apiUrl, path), {
    ...options,
    headers,
  });

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    let detail;
    if (typeof body === "object" && body) {
      const raw = body.detail ?? body;
      detail = typeof raw === "string" ? raw : JSON.stringify(raw);
    } else {
      detail = String(body);
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return body;
}

function card(title, className = "col-6") {
  const article = document.createElement("article");
  article.className = `card ${className}`;
  const h3 = document.createElement("h3");
  h3.textContent = title;
  const body = document.createElement("div");
  body.className = "card-body";
  article.append(h3, body);
  return { article, body };
}

function clearSection(id) {
  el.sections[id].innerHTML = "";
}

function sectionLoading(id, message = "Chargement...") {
  clearSection(id);
  const { article, body } = card("Chargement", "col-12");
  body.textContent = message;
  el.sections[id].appendChild(article);
}

function renderNav() {
  el.nav.innerHTML = "";
  for (const page of PAGES) {
    const btn = document.createElement("button");
    btn.textContent = page.label;
    btn.className = page.id === state.activePage ? "active" : "";
    btn.addEventListener("click", () => setActivePage(page.id));
    el.nav.appendChild(btn);
  }
}

function setActivePage(pageId) {
  state.activePage = pageId;
  for (const page of PAGES) {
    el.sections[page.id].classList.toggle("active", page.id === pageId);
  }
  const page = PAGES.find((p) => p.id === pageId);
  el.pageTitle.textContent = page.label;
  el.pageSubtitle.textContent = page.subtitle;
  renderNav();
  loadPage(pageId);
}

function toIsoOrNull(dateValue, timeValue = "00:00") {
  if (!dateValue) return null;
  const raw = `${dateValue}T${timeValue}:00`;
  return new Date(raw).toISOString();
}

function fmtDate(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("fr-FR");
}

function fmtMoney(amount, currency = "EUR") {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency }).format(Number(amount || 0));
}

function isoDateOnly(dateValue) {
  return new Date(dateValue.getFullYear(), dateValue.getMonth(), dateValue.getDate()).toISOString().slice(0, 10);
}

function getMonthBounds(baseDate) {
  const monthStart = new Date(baseDate.getFullYear(), baseDate.getMonth(), 1);
  const monthEnd = new Date(baseDate.getFullYear(), baseDate.getMonth() + 1, 0, 23, 59, 59, 999);
  return { monthStart, monthEnd };
}

function getCalendarGridBounds(monthStart) {
  const mondayIndex = (monthStart.getDay() + 6) % 7;
  const gridStart = new Date(monthStart.getFullYear(), monthStart.getMonth(), monthStart.getDate() - mondayIndex);
  const gridEnd = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + 41, 23, 59, 59, 999);
  return { gridStart, gridEnd };
}

function formatDayLabel(dateValue) {
  return dateValue.toLocaleDateString("fr-FR", { weekday: "long", day: "2-digit", month: "long" });
}

async function renderDashboard() {
  const section = el.sections.dashboard;
  sectionLoading("dashboard");

  try {
    const now = new Date();
    if (!state.dashboardMonthStart) {
      state.dashboardMonthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
    }
    if (!state.dashboardSelectedDay) {
      state.dashboardSelectedDay = isoDateOnly(now);
    }

    const monthView = new Date(state.dashboardMonthStart);
    const { monthStart } = getMonthBounds(monthView);
    const { gridStart, gridEnd } = getCalendarGridBounds(monthStart);
    const dayListParams = new URLSearchParams({
      from_at: gridStart.toISOString(),
      to_at: gridEnd.toISOString(),
      include_completed: "true",
      limit: "2000",
    });

    const [overviewRes, upcomingEvents, upcomingSubs, pantryOverview, calendarItems, mealPlans, recipes] = await Promise.all([
      api("/api/v1/skill/execute", {
        method: "POST",
        body: JSON.stringify({ action: "dashboard.overview", input: {} }),
      }),
      api("/api/v1/events/upcoming?days=7"),
      api("/api/v1/subscriptions/upcoming?days=30"),
      api("/api/v1/pantry/overview?days=7"),
      api(`/api/v1/calendar/items?${dayListParams.toString()}`),
      api(`/api/v1/meal-plans?date_from=${isoDateOnly(gridStart)}&date_to=${isoDateOnly(gridEnd)}&limit=400`),
      api("/api/v1/recipes?limit=200"),
    ]);

    section.innerHTML = "";
    const overview = overviewRes.data.overview;

    const summary = card("Vue generale", "col-12");
    summary.body.innerHTML = `
      <div class="kpis">
        <div class="kpi"><small>Open tasks</small><strong>${overview.open_tasks}</strong></div>
        <div class="kpi"><small>Overdue</small><strong>${overview.overdue_tasks}</strong></div>
        <div class="kpi"><small>Depenses mois</small><strong>${fmtMoney(overview.this_month_expense, "EUR")}</strong></div>
        <div class="kpi"><small>Courses a faire</small><strong>${overview.grocery_unchecked}</strong></div>
        <div class="kpi"><small>Habits actives</small><strong>${overview.active_habits}</strong></div>
        <div class="kpi"><small>Goals actives</small><strong>${overview.active_goals}</strong></div>
        <div class="kpi"><small>Events (7j)</small><strong>${overview.upcoming_events_7d}</strong></div>
        <div class="kpi"><small>Subscriptions</small><strong>${overview.active_subscriptions}</strong></div>
        <div class="kpi"><small>Pantry low stock</small><strong>${overview.low_stock_pantry_items}</strong></div>
        <div class="kpi"><small>Notes total</small><strong>${overview.notes_total}</strong></div>
      </div>
    `;

    const evCard = card("Evenements a venir (7 jours)", "col-6");
    const evList = document.createElement("div");
    evList.className = "list";
    if (!upcomingEvents.length) {
      evList.innerHTML = "<p>Aucun evenement a venir.</p>";
    } else {
      upcomingEvents.forEach((ev) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>${ev.title}</h4><p>${fmtDate(ev.start_at)} -> ${fmtDate(ev.end_at)}</p><span class="badge">${ev.type}</span>`;
        evList.appendChild(item);
      });
    }
    evCard.body.appendChild(evList);

    const subCard = card("Abonnements a venir (30 jours)", "col-6");
    const subList = document.createElement("div");
    subList.className = "list";
    if (!upcomingSubs.length) {
      subList.innerHTML = "<p>Aucun paiement a venir.</p>";
    } else {
      upcomingSubs.forEach((sub) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>${sub.name}</h4><p>${fmtMoney(sub.amount, sub.currency)} - ${sub.interval}</p><span class="badge">${sub.next_due_date}</span>`;
        subList.appendChild(item);
      });
    }
    subCard.body.appendChild(subList);

    const pantryCard = card("Pantry status", "col-12");
    pantryCard.body.innerHTML = `
      <div class="row">
        <span class="badge">Total items: ${pantryOverview.total_items}</span>
        <span class="badge">Low stock: ${pantryOverview.low_stock_items}</span>
        <span class="badge">Expire < 7j: ${pantryOverview.expiring_within_7_days}</span>
      </div>
    `;

    const itemsByDay = new Map();
    for (const item of calendarItems) {
      const key = isoDateOnly(new Date(item.start_at));
      if (!itemsByDay.has(key)) itemsByDay.set(key, []);
      itemsByDay.get(key).push(item);
    }
    for (const [key, list] of itemsByDay.entries()) {
      list.sort((a, b) => String(a.start_at).localeCompare(String(b.start_at)));
      itemsByDay.set(key, list);
    }

    const mealByDaySlot = new Map();
    const mealByDay = new Map();
    for (const plan of mealPlans) {
      const dayKey = plan.planned_for;
      mealByDaySlot.set(`${dayKey}|${plan.slot}`, plan);
      if (!mealByDay.has(dayKey)) mealByDay.set(dayKey, []);
      mealByDay.get(dayKey).push(plan);
    }

    const calendarCard = card("Calendrier hub (interactif)", "col-12");
    const calendarWrap = document.createElement("div");
    calendarWrap.className = "dashboard-calendar";

    const calendarTop = document.createElement("div");
    calendarTop.className = "row";
    const prev = document.createElement("button");
    prev.className = "btn";
    prev.textContent = "←";
    prev.addEventListener("click", () => {
      state.dashboardMonthStart = new Date(monthStart.getFullYear(), monthStart.getMonth() - 1, 1).toISOString();
      renderDashboard();
    });
    const next = document.createElement("button");
    next.className = "btn";
    next.textContent = "→";
    next.addEventListener("click", () => {
      state.dashboardMonthStart = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 1).toISOString();
      renderDashboard();
    });
    const goToday = document.createElement("button");
    goToday.className = "btn";
    goToday.textContent = "Aujourd'hui";
    goToday.addEventListener("click", () => {
      state.dashboardMonthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
      state.dashboardSelectedDay = isoDateOnly(now);
      renderDashboard();
    });
    const monthLabel = document.createElement("strong");
    monthLabel.textContent = monthStart.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
    calendarTop.append(prev, monthLabel, next, goToday);

    const weekdayRow = document.createElement("div");
    weekdayRow.className = "weekday-row";
    ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].forEach((label) => {
      const d = document.createElement("div");
      d.textContent = label;
      weekdayRow.appendChild(d);
    });

    const monthGrid = document.createElement("div");
    monthGrid.className = "month-grid";
    const todayKey = isoDateOnly(now);

    for (let i = 0; i < 42; i += 1) {
      const dayDate = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i);
      const dayKey = isoDateOnly(dayDate);
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "month-cell";
      if (dayDate.getMonth() !== monthStart.getMonth()) cell.classList.add("out-month");
      if (dayKey === state.dashboardSelectedDay) cell.classList.add("selected");
      if (dayKey === todayKey) cell.classList.add("today");
      cell.addEventListener("click", () => {
        state.dashboardSelectedDay = dayKey;
        renderDashboard();
      });

      const dayHead = document.createElement("div");
      dayHead.className = "month-cell-head";
      dayHead.innerHTML = `<strong>${dayDate.getDate()}</strong>`;
      cell.appendChild(dayHead);

      const dayMeals = document.createElement("div");
      dayMeals.className = "month-meals";
      ["breakfast", "lunch", "dinner"].forEach((slot) => {
        const plan = mealByDaySlot.get(`${dayKey}|${slot}`);
        const row = document.createElement("div");
        row.className = `meal-chip ${plan ? "filled" : ""}`;
        const short = slot === "breakfast" ? "B" : slot === "lunch" ? "L" : "D";
        row.textContent = `${short}: ${plan ? `${plan.cooked ? "ok " : ""}${plan.recipe_name}` : "-"}`;
        dayMeals.appendChild(row);
      });
      cell.appendChild(dayMeals);

      const entries = itemsByDay.get(dayKey) || [];
      const events = document.createElement("div");
      events.className = "month-events";
      entries.slice(0, 2).forEach((entry) => {
        const e = document.createElement("div");
        e.className = `month-event cat-${entry.category || "general"}`;
        e.textContent = `${entry.all_day ? "" : `${new Date(entry.start_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })} `}${entry.title}`;
        events.appendChild(e);
      });
      if (entries.length > 2) {
        const more = document.createElement("div");
        more.className = "month-more";
        more.textContent = `+${entries.length - 2}`;
        events.appendChild(more);
      }
      cell.appendChild(events);
      monthGrid.appendChild(cell);
    }

    const selectedKey = state.dashboardSelectedDay;
    const selectedParts = selectedKey.split("-").map((x) => Number(x));
    const selectedDate = new Date(selectedParts[0], selectedParts[1] - 1, selectedParts[2]);
    const selectedDayItems = itemsByDay.get(selectedKey) || [];

    const side = document.createElement("div");
    side.className = "day-panel";
    side.innerHTML = `<h4>${formatDayLabel(selectedDate)}</h4>`;

    const agendaList = document.createElement("div");
    agendaList.className = "list";
    if (!selectedDayItems.length) {
      agendaList.innerHTML = "<p>Aucune entree calendrier ce jour.</p>";
    } else {
      selectedDayItems.forEach((entry) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>${entry.title}</h4><p>${entry.all_day ? "all day" : fmtDate(entry.start_at)} - ${entry.category}</p>`;
        agendaList.appendChild(item);
      });
    }
    side.appendChild(agendaList);

    const mealPlanner = document.createElement("div");
    mealPlanner.className = "stack";
    mealPlanner.innerHTML = "<h4>Planifier les repas du jour</h4>";
    const sortedRecipes = [...recipes].sort((a, b) => String(a.name).localeCompare(String(b.name)));

    [
      { slot: "breakfast", label: "Petit dej" },
      { slot: "lunch", label: "Dejeuner" },
      { slot: "dinner", label: "Diner" },
    ].forEach(({ slot, label }) => {
      const existing = mealByDaySlot.get(`${selectedKey}|${slot}`);
      const row = document.createElement("div");
      row.className = "meal-slot-row";

      const title = document.createElement("strong");
      title.textContent = existing?.cooked ? `${label} (fait)` : label;

      const select = document.createElement("select");
      select.innerHTML = `<option value="">Choisir recette...</option>${sortedRecipes
        .map((r) => `<option value="${r.id}">#${r.id} ${r.name}</option>`)
        .join("")}`;
      if (existing) select.value = String(existing.recipe_id);

      const save = document.createElement("button");
      save.className = "btn btn-primary";
      save.textContent = existing ? "Mettre a jour" : "Planifier";
      save.addEventListener("click", async () => {
        const recipeId = Number(select.value || 0);
        if (!recipeId) {
          showToast("Choisis une recette", true);
          return;
        }
        try {
          if (existing) {
            await api(`/api/v1/meal-plans/${existing.id}`, {
              method: "PATCH",
              body: JSON.stringify({ recipe_id: recipeId }),
            });
          } else {
            await api("/api/v1/meal-plans", {
              method: "POST",
              body: JSON.stringify({
                planned_for: selectedKey,
                slot,
                recipe_id: recipeId,
                auto_add_missing_ingredients: true,
              }),
            });
          }
          await renderDashboard();
        } catch (err) {
          showToast(String(err.message || err), true);
        }
      });

      const rowActions = document.createElement("div");
      rowActions.className = "row";
      rowActions.append(save);
      if (existing) {
        const confirmBtn = document.createElement("button");
        confirmBtn.className = "btn btn-good";
        confirmBtn.textContent = existing.cooked ? "Deja fait" : "Confirmer fait";
        if (existing.cooked) {
          confirmBtn.disabled = true;
        } else {
          confirmBtn.addEventListener("click", async () => {
            try {
              await api(`/api/v1/meal-plans/${existing.id}/confirm-cooked`, { method: "POST", body: "{}" });
              showToast("Repas confirme, pantry mis a jour");
              await renderDashboard();
            } catch (err) {
              showToast(String(err.message || err), true);
            }
          });
        }

        const unconfirmBtn = document.createElement("button");
        unconfirmBtn.className = "btn";
        unconfirmBtn.textContent = existing.cooked ? "Annuler fait" : "Non fait";
        if (!existing.cooked) {
          unconfirmBtn.disabled = true;
        } else {
          unconfirmBtn.addEventListener("click", async () => {
            try {
              await api(`/api/v1/meal-plans/${existing.id}/unconfirm-cooked`, { method: "POST" });
              showToast("Confirmation retiree, pantry restaure");
              await renderDashboard();
            } catch (err) {
              showToast(String(err.message || err), true);
            }
          });
        }

        const syncBtn = document.createElement("button");
        syncBtn.className = "btn";
        syncBtn.textContent = "Sync courses";
        syncBtn.addEventListener("click", async () => {
          try {
            await api(`/api/v1/meal-plans/${existing.id}/sync-groceries`, { method: "POST", body: "{}" });
            showToast("Courses synchronisees");
            await renderDashboard();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });

        const clearBtn = document.createElement("button");
        clearBtn.className = "btn btn-danger";
        clearBtn.textContent = "Supprimer";
        clearBtn.addEventListener("click", async () => {
          try {
            await api(`/api/v1/meal-plans/${existing.id}`, { method: "DELETE", body: "{}" });
            await renderDashboard();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        rowActions.append(confirmBtn, unconfirmBtn, syncBtn, clearBtn);
      }

      row.append(title, select, rowActions);
      mealPlanner.appendChild(row);
    });
    side.appendChild(mealPlanner);

    calendarWrap.append(calendarTop, weekdayRow, monthGrid, side);
    calendarCard.body.appendChild(calendarWrap);

    section.append(summary.article, calendarCard.article, evCard.article, subCard.article, pantryCard.article);
  } catch (err) {
    showPageError(section, err);
  }
}

function showPageError(section, err) {
  section.innerHTML = "";
  const { article, body } = card("Erreur", "col-12");
  const message = String(err.message || err);
  if (message.toLowerCase().includes("invalid api key")) {
    body.innerHTML = `<p>API key invalide. Configure une cle valide dans la barre de gauche puis clique "Tester connexion".</p>`;
  } else {
    body.innerHTML = `<p>${message}</p>`;
  }
  section.appendChild(article);
}

function bindFormSubmit(form, fn) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await fn(new FormData(form));
      showToast("Operation terminee");
    } catch (err) {
      showToast(String(err.message || err), true);
    }
  });
}

function makeList(items, renderItem) {
  const list = document.createElement("div");
  list.className = "list";
  if (!items.length) {
    list.innerHTML = "<p>Aucun element.</p>";
    return list;
  }
  items.forEach((item) => list.appendChild(renderItem(item)));
  return list;
}

async function renderTasks() {
  const section = el.sections.tasks;
  sectionLoading("tasks");
  try {
    const tasks = await api("/api/v1/tasks?limit=80");
    section.innerHTML = "";

    const create = card("Nouvelle tache", "col-5");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="title" placeholder="Titre" required class="full" />
      <input name="dueDate" type="date" />
      <select name="priority">
        <option value="medium">medium</option>
        <option value="low">low</option>
        <option value="high">high</option>
        <option value="urgent">urgent</option>
      </select>
      <textarea name="description" class="full" placeholder="Description"></textarea>
      <input name="tags" class="full" placeholder="tags: work,urgent" />
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: fd.get("title"),
          due_at: toIsoOrNull(fd.get("dueDate")),
          priority: fd.get("priority"),
          description: fd.get("description") || null,
          tags: String(fd.get("tags") || "")
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
        }),
      });
      await renderTasks();
    });
    create.body.appendChild(form);

    const listCard = card("Liste", "col-7");
    listCard.body.appendChild(
      makeList(tasks, (task) => {
        const item = document.createElement("div");
        item.className = "item";

        const top = document.createElement("div");
        top.className = "row";
        top.innerHTML = `<h4>#${task.id} ${task.title}</h4><span class="badge">${task.status}</span><span class="badge">${task.priority}</span>`;

        const p = document.createElement("p");
        p.textContent = `Due: ${task.due_at ? fmtDate(task.due_at) : "-"}`;

        const actions = document.createElement("div");
        actions.className = "row";
        const doneBtn = document.createElement("button");
        doneBtn.className = "btn btn-good";
        doneBtn.textContent = "Complete";
        doneBtn.disabled = task.status === "done";
        doneBtn.addEventListener("click", async () => {
          try {
            await api(`/api/v1/tasks/${task.id}/complete`, { method: "POST", body: "{}" });
            showToast("Tache completee");
            await renderTasks();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });

        const progressBtn = document.createElement("button");
        progressBtn.className = "btn";
        progressBtn.textContent = "In progress";
        progressBtn.addEventListener("click", async () => {
          try {
            await api(`/api/v1/tasks/${task.id}`, {
              method: "PATCH",
              body: JSON.stringify({ status: "in_progress" }),
            });
            showToast("Statut mis a jour");
            await renderTasks();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });

        actions.append(doneBtn, progressBtn);
        item.append(top, p, actions);
        return item;
      })
    );

    section.append(create.article, listCard.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderFinances() {
  const section = el.sections.finances;
  sectionLoading("finances");
  try {
    const now = new Date();
    const year = now.getUTCFullYear();
    const month = now.getUTCMonth() + 1;

    const [txs, summary, budgets] = await Promise.all([
      api("/api/v1/finances/transactions?limit=30"),
      api(`/api/v1/finances/summary?year=${year}&month=${month}`),
      api("/api/v1/finances/budgets"),
    ]);

    section.innerHTML = "";

    const addTx = card("Nouvelle transaction", "col-4");
    const txForm = document.createElement("form");
    txForm.className = "form-grid";
    txForm.innerHTML = `
      <select name="kind"><option value="expense">expense</option><option value="income">income</option></select>
      <input name="amount" type="number" step="0.01" min="0" placeholder="Montant" required />
      <input name="currency" value="EUR" />
      <input name="category" placeholder="Categorie" required />
      <input name="occurredDate" type="date" />
      <textarea name="note" class="full" placeholder="Note"></textarea>
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(txForm, async (fd) => {
      await api("/api/v1/finances/transactions", {
        method: "POST",
        body: JSON.stringify({
          kind: fd.get("kind"),
          amount: Number(fd.get("amount")),
          currency: fd.get("currency") || "EUR",
          category: fd.get("category"),
          occurred_at: toIsoOrNull(fd.get("occurredDate")),
          note: fd.get("note") || null,
          is_recurring: false,
        }),
      });
      await renderFinances();
    });
    addTx.body.appendChild(txForm);

    const summaryCard = card("Resume du mois", "col-4");
    summaryCard.body.innerHTML = `
      <div class="stack">
        <div class="kpi"><small>Income</small><strong>${fmtMoney(summary.income)}</strong></div>
        <div class="kpi"><small>Expense</small><strong>${fmtMoney(summary.expense)}</strong></div>
        <div class="kpi"><small>Net</small><strong>${fmtMoney(summary.net)}</strong></div>
      </div>
    `;

    const budgetCard = card("Budgets", "col-4");
    budgetCard.body.appendChild(
      makeList(budgets.slice(0, 8), (b) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>${b.month} - ${b.category}</h4><p>${fmtMoney(b.monthly_limit, b.currency)}</p>`;
        return item;
      })
    );

    const listCard = card("Dernieres transactions", "col-12");
    listCard.body.appendChild(
      makeList(txs, (tx) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>#${tx.id} ${tx.category}</h4><p>${fmtMoney(tx.amount, tx.currency)} - ${tx.kind} - ${fmtDate(tx.occurred_at)}</p>`;
        return item;
      })
    );

    section.append(addTx.article, summaryCard.article, budgetCard.article, listCard.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderGroceries() {
  const section = el.sections.groceries;
  sectionLoading("groceries");
  try {
    const items = await api("/api/v1/groceries?limit=300");
    section.innerHTML = "";

    const addCard = card("Ajouter produit", "col-4");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="name" placeholder="Nom" required class="full" />
      <input name="quantity" type="number" step="0.01" value="1" />
      <input name="unit" value="item" />
      <input name="category" placeholder="Categorie" />
      <input name="priority" type="number" min="1" max="5" value="3" />
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/groceries", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          quantity: Number(fd.get("quantity")),
          unit: fd.get("unit") || "item",
          category: fd.get("category") || null,
          priority: Number(fd.get("priority") || 3),
        }),
      });
      await renderGroceries();
    });
    addCard.body.appendChild(form);

    const listCard = card("Liste de courses", "col-8");
    listCard.body.appendChild(
      makeList(items, (g) => {
        const item = document.createElement("div");
        item.className = "item";
        const check = document.createElement("button");
        check.className = `btn ${g.checked ? "" : "btn-good"}`;
        check.textContent = g.checked ? "Uncheck" : "Check";
        check.addEventListener("click", async () => {
          try {
            await api(`/api/v1/groceries/${g.id}`, {
              method: "PATCH",
              body: JSON.stringify({ checked: !g.checked }),
            });
            await renderGroceries();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });

        const del = document.createElement("button");
        del.className = "btn btn-danger";
        del.textContent = "Supprimer";
        del.addEventListener("click", async () => {
          try {
            await api(`/api/v1/groceries/${g.id}`, { method: "DELETE", body: "{}" });
            await renderGroceries();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });

        item.innerHTML = `<h4>#${g.id} ${g.name}</h4><p>${g.quantity} ${g.unit} - ${g.category || "general"}</p>`;
        const actions = document.createElement("div");
        actions.className = "row";
        actions.append(check, del);
        item.appendChild(actions);
        return item;
      })
    );

    section.append(addCard.article, listCard.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderRecipes() {
  const section = el.sections.recipes;
  sectionLoading("recipes");
  try {
    const recipes = await api("/api/v1/recipes?limit=80");
    section.innerHTML = "";

    const add = card("Nouvelle recette", "col-5");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="name" class="full" placeholder="Nom recette" required />
      <input name="prep" type="number" min="0" value="10" />
      <input name="cook" type="number" min="0" value="15" />
      <textarea name="instructions" class="full" placeholder="Instructions" required></textarea>
      <input name="tags" class="full" placeholder="tags: dinner,quick" />
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/recipes", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          instructions: fd.get("instructions"),
          prep_minutes: Number(fd.get("prep")),
          cook_minutes: Number(fd.get("cook")),
          tags: String(fd.get("tags") || "")
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          ingredients: [],
        }),
      });
      await renderRecipes();
    });
    add.body.appendChild(form);

    const list = card("Recettes", "col-7");
    list.body.appendChild(
      makeList(recipes, (r) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>#${r.id} ${r.name}</h4><p>${r.prep_minutes + r.cook_minutes} min - servings ${r.servings}</p><p>${(r.instructions || "").slice(0, 120)}</p>`;
        return item;
      })
    );

    section.append(add.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderMealPlans() {
  const section = el.sections["meal-plans"];
  sectionLoading("meal-plans");
  try {
    const now = new Date();
    const dateFrom = now.toISOString().slice(0, 10);
    const in14 = new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    const [recipes, plans] = await Promise.all([
      api("/api/v1/recipes?limit=200"),
      api(`/api/v1/meal-plans?date_from=${dateFrom}&date_to=${in14}&limit=200`),
    ]);

    section.innerHTML = "";
    const add = card("Planifier un repas", "col-5");
    if (!recipes.length) {
      add.body.innerHTML = "<p>Ajoute d'abord une recette avec ses ingredients.</p>";
    } else {
      const form = document.createElement("form");
      form.className = "form-grid";
      form.innerHTML = `
        <input name="planned_for" type="date" required />
        <select name="slot">
          <option value="breakfast">breakfast</option>
          <option value="lunch">lunch</option>
          <option value="dinner">dinner</option>
        </select>
        <select name="recipe_id" class="full">${recipes
          .map((r) => `<option value="${r.id}">#${r.id} ${r.name}</option>`)
          .join("")}</select>
        <input name="servings_override" type="number" min="1" placeholder="Servings (optional)" />
        <label class="full"><input name="auto_add" type="checkbox" checked /> Ajouter auto les ingredients manquants aux courses</label>
        <textarea name="note" class="full" placeholder="Note"></textarea>
        <button class="btn btn-primary full" type="submit">Planifier</button>
      `;
      bindFormSubmit(form, async (fd) => {
        await api("/api/v1/meal-plans", {
          method: "POST",
          body: JSON.stringify({
            planned_for: fd.get("planned_for"),
            slot: fd.get("slot"),
            recipe_id: Number(fd.get("recipe_id")),
            servings_override: fd.get("servings_override") ? Number(fd.get("servings_override")) : null,
            note: fd.get("note") || null,
            auto_add_missing_ingredients: Boolean(fd.get("auto_add")),
          }),
        });
        await renderMealPlans();
      });
      add.body.appendChild(form);
    }

    const list = card("Planning 14 jours", "col-7");
    list.body.appendChild(
      makeList(plans, (p) => {
        const item = document.createElement("div");
        item.className = "item";
        const missing = p.missing_ingredients || [];
        item.innerHTML = `<h4>${p.planned_for} - ${p.slot} - ${p.recipe_name}</h4>
          <p>servings: ${p.servings_override || "-"} | auto: ${p.auto_add_missing_ingredients ? "yes" : "no"} | sync: ${p.synced_grocery_at ? fmtDate(p.synced_grocery_at) : "-"}</p>
          <p>cooked: ${p.cooked ? `yes (${p.cooked_at ? fmtDate(p.cooked_at) : "-"})` : "no"}</p>
          <p>Manquants: ${missing.length ? missing.map((m) => `${m.name} (${m.missing_quantity} ${m.unit})`).join(", ") : "aucun"}</p>`;

        const confirm = document.createElement("button");
        confirm.className = "btn btn-good";
        confirm.textContent = p.cooked ? "Deja fait" : "Confirmer fait";
        if (p.cooked) {
          confirm.disabled = true;
        } else {
          confirm.addEventListener("click", async () => {
            try {
              await api(`/api/v1/meal-plans/${p.id}/confirm-cooked`, { method: "POST", body: "{}" });
              await renderMealPlans();
            } catch (err) {
              showToast(String(err.message || err), true);
            }
          });
        }
        item.appendChild(confirm);

        const unconfirm = document.createElement("button");
        unconfirm.className = "btn";
        unconfirm.textContent = p.cooked ? "Annuler fait" : "Non fait";
        if (!p.cooked) {
          unconfirm.disabled = true;
        } else {
          unconfirm.addEventListener("click", async () => {
            try {
              await api(`/api/v1/meal-plans/${p.id}/unconfirm-cooked`, { method: "POST" });
              await renderMealPlans();
            } catch (err) {
              showToast(String(err.message || err), true);
            }
          });
        }
        item.appendChild(unconfirm);

        const sync = document.createElement("button");
        sync.className = "btn";
        sync.textContent = "Sync courses";
        sync.addEventListener("click", async () => {
          try {
            await api(`/api/v1/meal-plans/${p.id}/sync-groceries`, { method: "POST", body: "{}" });
            await renderMealPlans();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        item.appendChild(sync);
        return item;
      })
    );

    section.append(add.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderHabits() {
  const section = el.sections.habits;
  sectionLoading("habits");
  try {
    const habits = await api("/api/v1/habits?active_only=true");
    section.innerHTML = "";

    const add = card("Nouvelle habitude", "col-4");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="name" placeholder="Nom" required class="full" />
      <select name="frequency"><option value="daily">daily</option><option value="weekly">weekly</option></select>
      <input name="target" type="number" min="1" value="1" />
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/habits", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          frequency: fd.get("frequency"),
          target_per_period: Number(fd.get("target") || 1),
        }),
      });
      await renderHabits();
    });
    add.body.appendChild(form);

    const list = card("Habitudes actives", "col-8");
    list.body.appendChild(
      makeList(habits, (h) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>#${h.id} ${h.name}</h4><p>${h.frequency} - streak ${h.streak}</p>`;
        const logBtn = document.createElement("button");
        logBtn.className = "btn btn-good";
        logBtn.textContent = "Log +1";
        logBtn.addEventListener("click", async () => {
          try {
            await api(`/api/v1/habits/${h.id}/logs`, {
              method: "POST",
              body: JSON.stringify({ value: 1 }),
            });
            await renderHabits();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        item.appendChild(logBtn);
        return item;
      })
    );

    section.append(add.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderGoals() {
  const section = el.sections.goals;
  sectionLoading("goals");
  try {
    const goals = await api("/api/v1/goals?limit=100");
    section.innerHTML = "";

    const add = card("Nouvel objectif", "col-4");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="title" placeholder="Titre" required class="full" />
      <select name="status"><option value="planned">planned</option><option value="active">active</option><option value="paused">paused</option></select>
      <input name="progress" type="number" min="0" max="100" value="0" />
      <input name="target" type="date" class="full" />
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/goals", {
        method: "POST",
        body: JSON.stringify({
          title: fd.get("title"),
          status: fd.get("status"),
          progress_percent: Number(fd.get("progress") || 0),
          target_date: fd.get("target") || null,
        }),
      });
      await renderGoals();
    });
    add.body.appendChild(form);

    const list = card("Objectifs", "col-8");
    list.body.appendChild(
      makeList(goals, (g) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>#${g.id} ${g.title}</h4><p>Status ${g.status} - progress ${g.progress_percent}% - target ${g.target_date || "-"}</p>`;
        const row = document.createElement("div");
        row.className = "row";
        const bump = document.createElement("button");
        bump.className = "btn";
        bump.textContent = "+10%";
        bump.addEventListener("click", async () => {
          try {
            const next = Math.min(100, (g.progress_percent || 0) + 10);
            await api(`/api/v1/goals/${g.id}`, {
              method: "PATCH",
              body: JSON.stringify({ progress_percent: next, status: next === 100 ? "completed" : g.status }),
            });
            await renderGoals();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        row.appendChild(bump);
        item.appendChild(row);
        return item;
      })
    );

    section.append(add.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderEvents() {
  const section = el.sections.events;
  sectionLoading("events");
  try {
    const events = await api("/api/v1/events/upcoming?days=30");
    section.innerHTML = "";

    const add = card("Nouvel evenement", "col-5");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="title" placeholder="Titre" required class="full" />
      <input name="startDate" type="date" required />
      <input name="startTime" type="time" value="09:00" />
      <input name="endDate" type="date" required />
      <input name="endTime" type="time" value="10:00" />
      <select name="type" class="full">
        <option value="personal">personal</option>
        <option value="work">work</option>
        <option value="health">health</option>
        <option value="finance">finance</option>
        <option value="social">social</option>
      </select>
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/events", {
        method: "POST",
        body: JSON.stringify({
          title: fd.get("title"),
          start_at: toIsoOrNull(fd.get("startDate"), fd.get("startTime") || "00:00"),
          end_at: toIsoOrNull(fd.get("endDate"), fd.get("endTime") || "00:00"),
          type: fd.get("type"),
        }),
      });
      await renderEvents();
    });
    add.body.appendChild(form);

    const list = card("Prochains evenements (30j)", "col-7");
    list.body.appendChild(
      makeList(events, (ev) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>#${ev.id} ${ev.title}</h4><p>${fmtDate(ev.start_at)} -> ${fmtDate(ev.end_at)}</p><span class="badge">${ev.type}</span>`;
        const del = document.createElement("button");
        del.className = "btn btn-danger";
        del.textContent = "Delete";
        del.addEventListener("click", async () => {
          try {
            await api(`/api/v1/events/${ev.id}`, { method: "DELETE", body: "{}" });
            await renderEvents();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        item.appendChild(del);
        return item;
      })
    );

    section.append(add.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderCalendar() {
  const section = el.sections.calendar;
  sectionLoading("calendar");
  try {
    const today = new Date().toISOString().slice(0, 10);
    const [agenda, reminders] = await Promise.all([
      api(`/api/v1/calendar/agenda?day=${today}&include_completed=false`),
      api("/api/v1/calendar/reminders/due?within_minutes=180"),
    ]);
    section.innerHTML = "";

    const sync = card("Sync calendrier depuis modules", "col-4");
    sync.body.innerHTML = `<p>Projette tasks/events/subscriptions/meal-plans dans un calendrier unifie.</p>`;
    const syncBtn = document.createElement("button");
    syncBtn.className = "btn btn-primary";
    syncBtn.textContent = "Synchroniser";
    syncBtn.addEventListener("click", async () => {
      try {
        await api("/api/v1/calendar/sync", { method: "POST", body: "{}" });
        await renderCalendar();
      } catch (err) {
        showToast(String(err.message || err), true);
      }
    });
    const ics = document.createElement("a");
    ics.className = "btn";
    ics.href = `${getConfig().apiUrl.replace(/\/$/, "")}/api/v1/calendar/export.ics`;
    ics.target = "_blank";
    ics.rel = "noreferrer";
    ics.textContent = "Exporter ICS";
    sync.body.append(syncBtn, ics);

    const add = card("Ajouter entree calendrier", "col-4");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="title" class="full" placeholder="Titre" required />
      <input name="startDate" type="date" required />
      <input name="startTime" type="time" value="09:00" />
      <input name="endDate" type="date" required />
      <input name="endTime" type="time" value="10:00" />
      <select name="category" class="full">
        <option value="general">general</option>
        <option value="task">task</option>
        <option value="event">event</option>
        <option value="subscription">subscription</option>
        <option value="meal">meal</option>
      </select>
      <input name="reminders" class="full" placeholder="Offsets min ex: 1440,120,30" value="60" />
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/calendar/items", {
        method: "POST",
        body: JSON.stringify({
          title: fd.get("title"),
          start_at: toIsoOrNull(fd.get("startDate"), fd.get("startTime") || "00:00"),
          end_at: toIsoOrNull(fd.get("endDate"), fd.get("endTime") || "00:00"),
          category: fd.get("category"),
          reminder_offsets_min: String(fd.get("reminders") || "60")
            .split(",")
            .map((x) => Number(x.trim()))
            .filter((n) => Number.isFinite(n) && n >= 0),
        }),
      });
      await renderCalendar();
    });
    add.body.appendChild(form);

    const rem = card("Rappels a venir (3h)", "col-4");
    rem.body.appendChild(
      makeList(reminders, (r) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>${r.item.title}</h4><p>due ${fmtDate(r.due_at)} (${r.minutes_before} min avant)</p>`;
        const ack = document.createElement("button");
        ack.className = "btn";
        ack.textContent = "Ack";
        ack.addEventListener("click", async () => {
          try {
            await api(`/api/v1/calendar/reminders/${r.item.id}/ack`, { method: "POST", body: "{}" });
            await renderCalendar();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        item.appendChild(ack);
        return item;
      })
    );

    const list = card(`Agenda du jour (${today})`, "col-12");
    list.body.appendChild(
      makeList(agenda, (a) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>#${a.id} ${a.title}</h4><p>${fmtDate(a.start_at)} -> ${fmtDate(a.end_at)} | ${a.category} | ${a.source}</p>`;
        const toggle = document.createElement("button");
        toggle.className = "btn";
        toggle.textContent = a.completed ? "Mark open" : "Mark done";
        toggle.addEventListener("click", async () => {
          try {
            await api(`/api/v1/calendar/items/${a.id}`, {
              method: "PATCH",
              body: JSON.stringify({ completed: !a.completed }),
            });
            await renderCalendar();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        item.appendChild(toggle);
        return item;
      })
    );

    section.append(sync.article, add.article, rem.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderSubscriptions() {
  const section = el.sections.subscriptions;
  sectionLoading("subscriptions");
  try {
    const [subs, projection] = await Promise.all([
      api("/api/v1/subscriptions?active_only=false&limit=300"),
      api("/api/v1/subscriptions/projection?currency=EUR"),
    ]);

    section.innerHTML = "";

    const add = card("Nouvel abonnement", "col-4");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="name" placeholder="Nom" required class="full" />
      <input name="amount" type="number" step="0.01" min="0" placeholder="Montant" required />
      <input name="currency" value="EUR" />
      <select name="interval">
        <option value="monthly">monthly</option>
        <option value="weekly">weekly</option>
        <option value="yearly">yearly</option>
      </select>
      <input name="nextDue" type="date" class="full" required />
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          amount: Number(fd.get("amount")),
          currency: fd.get("currency") || "EUR",
          interval: fd.get("interval"),
          next_due_date: fd.get("nextDue"),
        }),
      });
      await renderSubscriptions();
    });
    add.body.appendChild(form);

    const proj = card("Projection", "col-3");
    proj.body.innerHTML = `
      <div class="kpi"><small>Monthly</small><strong>${fmtMoney(projection.monthly_total, projection.currency)}</strong></div>
      <div class="kpi"><small>Yearly</small><strong>${fmtMoney(projection.yearly_total, projection.currency)}</strong></div>
    `;

    const list = card("Abonnements", "col-5");
    list.body.appendChild(
      makeList(subs, (s) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>#${s.id} ${s.name}</h4><p>${fmtMoney(s.amount, s.currency)} - ${s.interval} - due ${s.next_due_date}</p><span class="badge">${s.active ? "active" : "inactive"}</span>`;
        const toggle = document.createElement("button");
        toggle.className = "btn";
        toggle.textContent = s.active ? "Deactivate" : "Activate";
        toggle.addEventListener("click", async () => {
          try {
            await api(`/api/v1/subscriptions/${s.id}`, {
              method: "PATCH",
              body: JSON.stringify({ active: !s.active }),
            });
            await renderSubscriptions();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        item.appendChild(toggle);
        return item;
      })
    );

    section.append(add.article, proj.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderPantry() {
  const section = el.sections.pantry;
  sectionLoading("pantry");
  try {
    const [items, overview] = await Promise.all([
      api("/api/v1/pantry/items?limit=500"),
      api("/api/v1/pantry/overview?days=7"),
    ]);
    section.innerHTML = "";

    const add = card("Ajouter stock", "col-4");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="name" placeholder="Nom" required class="full" />
      <input name="quantity" type="number" step="0.01" value="1" />
      <input name="unit" value="item" />
      <input name="min" type="number" step="0.01" value="0" />
      <input name="expires" type="date" class="full" />
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/pantry/items", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          quantity: Number(fd.get("quantity") || 0),
          unit: fd.get("unit") || "item",
          min_quantity: Number(fd.get("min") || 0),
          expires_at: fd.get("expires") || null,
        }),
      });
      await renderPantry();
    });
    add.body.appendChild(form);

    const over = card("Pantry overview", "col-3");
    over.body.innerHTML = `
      <div class="kpi"><small>Total</small><strong>${overview.total_items}</strong></div>
      <div class="kpi"><small>Low stock</small><strong>${overview.low_stock_items}</strong></div>
      <div class="kpi"><small>Expire < 7j</small><strong>${overview.expiring_within_7_days}</strong></div>
    `;

    const list = card("Items", "col-5");
    list.body.appendChild(
      makeList(items, (p) => {
        const item = document.createElement("div");
        item.className = "item";
        const low = Number(p.quantity) <= Number(p.min_quantity);
        item.innerHTML = `<h4>#${p.id} ${p.name}</h4><p>${p.quantity} ${p.unit} (min ${p.min_quantity}) ${low ? "- LOW" : ""}</p>`;
        const consume = document.createElement("button");
        consume.className = "btn";
        consume.textContent = "Consume";
        consume.addEventListener("click", async () => {
          const amount = Number(prompt("Amount to consume", "1") || "0");
          if (!amount || amount <= 0) return;
          try {
            await api(`/api/v1/pantry/items/${p.id}/consume`, {
              method: "POST",
              body: JSON.stringify({ amount }),
            });
            await renderPantry();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        const del = document.createElement("button");
        del.className = "btn btn-danger";
        del.textContent = "Supprimer";
        del.addEventListener("click", async () => {
          try {
            await api(`/api/v1/pantry/items/${p.id}`, { method: "DELETE", body: "{}" });
            await renderPantry();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        const actions = document.createElement("div");
        actions.className = "row";
        actions.append(consume, del);
        item.appendChild(actions);
        return item;
      })
    );

    section.append(add.article, over.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderNotes() {
  const section = el.sections.notes;
  sectionLoading("notes");
  try {
    const notes = await api("/api/v1/notes?limit=200");
    section.innerHTML = "";

    const add = card("Nouvelle note", "col-5");
    const form = document.createElement("form");
    form.className = "form-grid";
    form.innerHTML = `
      <input name="title" class="full" placeholder="Titre" required />
      <select name="kind">
        <option value="note">note</option>
        <option value="journal">journal</option>
        <option value="idea">idea</option>
      </select>
      <input name="mood" type="number" min="1" max="10" placeholder="Mood" />
      <textarea name="content" class="full" placeholder="Contenu" required></textarea>
      <button class="btn btn-primary full" type="submit">Ajouter</button>
    `;
    bindFormSubmit(form, async (fd) => {
      await api("/api/v1/notes", {
        method: "POST",
        body: JSON.stringify({
          title: fd.get("title"),
          content: fd.get("content"),
          kind: fd.get("kind"),
          mood: fd.get("mood") ? Number(fd.get("mood")) : null,
        }),
      });
      await renderNotes();
    });
    add.body.appendChild(form);

    const list = card("Notes", "col-7");
    list.body.appendChild(
      makeList(notes, (n) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>#${n.id} ${n.title}</h4><p>${n.kind} ${n.mood ? `- mood ${n.mood}` : ""}</p><p>${(n.content || "").slice(0, 160)}</p>`;
        const del = document.createElement("button");
        del.className = "btn btn-danger";
        del.textContent = "Delete";
        del.addEventListener("click", async () => {
          try {
            await api(`/api/v1/notes/${n.id}`, { method: "DELETE", body: "{}" });
            await renderNotes();
          } catch (err) {
            showToast(String(err.message || err), true);
          }
        });
        item.appendChild(del);
        return item;
      })
    );

    section.append(add.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderLinear() {
  const section = el.sections.linear;
  sectionLoading("linear");
  try {
    const [projects, issues] = await Promise.all([
      api("/api/v1/linear/projects?source=cache&limit=200"),
      api("/api/v1/linear/issues?source=cache&limit=200"),
    ]);

    section.innerHTML = "";

    const syncCard = card("Sync Linear", "col-4");
    const syncBtn = document.createElement("button");
    syncBtn.className = "btn btn-primary";
    syncBtn.textContent = "Synchroniser maintenant";
    syncBtn.addEventListener("click", async () => {
      try {
        await api("/api/v1/linear/sync", { method: "POST", body: "{}" });
        await renderLinear();
      } catch (err) {
        showToast(String(err.message || err), true);
      }
    });
    syncCard.body.innerHTML = `<p>Projects cache: ${projects.length}</p><p>Issues cache: ${issues.length}</p>`;
    syncCard.body.appendChild(syncBtn);

    const create = card("Creer ticket Linear", "col-4");
    const createForm = document.createElement("form");
    createForm.className = "form-grid";
    createForm.innerHTML = `
      <input name="title" class="full" placeholder="Titre issue" required />
      <select name="project_id" class="full">
        <option value="">Sans projet</option>
        ${projects.map((p) => `<option value="${p.id}">${p.name}</option>`).join("")}
      </select>
      <input name="team_id" class="full" placeholder="Team ID (optionnel)" />
      <input name="priority" type="number" min="0" max="4" placeholder="Priority 0..4" />
      <input name="due_date" type="date" />
      <textarea name="description" class="full" placeholder="Description"></textarea>
      <button class="btn btn-primary full" type="submit">Creer</button>
    `;
    bindFormSubmit(createForm, async (fd) => {
      await api("/api/v1/linear/issues", {
        method: "POST",
        body: JSON.stringify({
          title: fd.get("title"),
          description: fd.get("description") || null,
          project_id: fd.get("project_id") || null,
          team_id: fd.get("team_id") || null,
          priority: fd.get("priority") ? Number(fd.get("priority")) : null,
          due_date: fd.get("due_date") || null,
        }),
      });
      await renderLinear();
    });
    create.body.appendChild(createForm);

    const list = card("Issues cachees", "col-4");
    list.body.appendChild(
      makeList(issues, (issue) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>${issue.identifier || issue.id} - ${issue.title}</h4>
          <p>${issue.state || "-"} | P${issue.priority ?? "-"} | due ${issue.due_date || "-"}</p>
          <p>${issue.assignee_name || "unassigned"}</p>`;
        return item;
      })
    );

    section.append(syncCard.article, create.article, list.article);
  } catch (err) {
    showPageError(section, err);
  }
}

async function renderAIConsole() {
  const section = el.sections.ai;
  clearSection("ai");

  const execCard = card("Skill execute", "col-6");
  const form = document.createElement("form");
  form.className = "stack";
  form.innerHTML = `
    <input name="action" placeholder="action ex: dashboard.overview" required />
    <textarea name="payload" class="mono" placeholder='{"year":2026,"month":3}'>{}</textarea>
    <button class="btn btn-primary" type="submit">Executer</button>
  `;

  const output = document.createElement("pre");
  output.className = "item mono";
  output.style.whiteSpace = "pre-wrap";
  output.textContent = "Resultat...";

  bindFormSubmit(form, async (fd) => {
    let input = {};
    const raw = String(fd.get("payload") || "{}").trim();
    if (raw) input = JSON.parse(raw);
    const res = await api("/api/v1/skill/execute", {
      method: "POST",
      body: JSON.stringify({
        action: fd.get("action"),
        input,
      }),
    });
    output.textContent = JSON.stringify(res, null, 2);
  });

  execCard.body.append(form, output);

  const helper = card("Actions disponibles", "col-6");
  try {
    const manifest = await api("/api/v1/skill/manifest");
    helper.body.appendChild(
      makeList(manifest.actions || [], (a) => {
        const item = document.createElement("div");
        item.className = "item";
        item.innerHTML = `<h4>${a.action}</h4><p>${a.description || ""}</p>`;
        return item;
      })
    );
  } catch (err) {
    helper.body.innerHTML = `<p>${String(err.message || err)}</p>`;
  }

  section.append(execCard.article, helper.article);
}

const pageLoaders = {
  dashboard: renderDashboard,
  tasks: renderTasks,
  finances: renderFinances,
  groceries: renderGroceries,
  recipes: renderRecipes,
  "meal-plans": renderMealPlans,
  habits: renderHabits,
  goals: renderGoals,
  events: renderEvents,
  calendar: renderCalendar,
  subscriptions: renderSubscriptions,
  pantry: renderPantry,
  notes: renderNotes,
  linear: renderLinear,
  ai: renderAIConsole,
};

async function loadPage(pageId) {
  const loader = pageLoaders[pageId];
  if (!loader) return;
  await loader();
}

function initConfigUI() {
  const cfg = getConfig();
  el.apiUrl.value = cfg.apiUrl;
  el.apiKey.value = cfg.apiKey || "change-me";
  if (!localStorage.getItem(STORAGE_KEYS.apiUrl)) {
    localStorage.setItem(STORAGE_KEYS.apiUrl, normalizeApiUrl(el.apiUrl.value));
  }
  if (!localStorage.getItem(STORAGE_KEYS.apiKey) && el.apiKey.value.trim()) {
    localStorage.setItem(STORAGE_KEYS.apiKey, normalizeApiKey(el.apiKey.value));
  }
  el.saveConfigBtn.addEventListener("click", saveConfig);
  el.testConfigBtn.addEventListener("click", testConnection);
}

function initRefreshButton() {
  el.refreshAllBtn.addEventListener("click", () => loadPage(state.activePage));
}

function boot() {
  initConfigUI();
  initRefreshButton();
  renderNav();
  setActivePage("dashboard");
}

boot();
