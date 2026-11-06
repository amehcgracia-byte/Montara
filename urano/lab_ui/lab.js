/* U12b: isolated browser UI for laboratory HTTP contracts, not Engine editing. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const ui = {
    csrf: null, projects: [], current: null, mode: "login", busy: false
  };
  const notice = message => { $("notice").textContent = message || ""; };
  const busy = value => {
    ui.busy = value;
    for (const id of ["submitAuth", "saveNotes", "logoutBtn"]) $(id).disabled = value;
    $("newProjectForm").querySelector("button").disabled = value;
  };

  async function request(path, { method = "GET", body, csrf = false } = {}) {
    const headers = { "Accept": "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (csrf) headers["X-Urano-CSRF"] = ui.csrf || "";
    const response = await fetch("/urano/v1" + path, {
      method, credentials: "same-origin", headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(result.error || "No se pudo completar la operación.");
      error.status = response.status;
      throw error;
    }
    return result;
  }

  function mode(next) {
    ui.mode = next;
    $("loginTab").setAttribute("aria-pressed", String(next === "login"));
    $("registerTab").setAttribute("aria-pressed", String(next === "register"));
    $("submitAuth").textContent = next === "login" ? "Entrar" : "Crear cuenta de prueba";
    $("authForm").elements.password.autocomplete =
      next === "login" ? "current-password" : "new-password";
    notice("");
  }
  $("loginTab").addEventListener("click", () => mode("login"));
  $("registerTab").addEventListener("click", () => mode("register"));

  function signedIn(value) {
    $("authPanel").hidden = value;
    $("projectsPanel").hidden = !value;
    if (!value) {
      ui.csrf = null;
      ui.current = null;
      ui.projects = [];
      $("projectList").replaceChildren();
      $("projectDetail").hidden = true;
    }
  }
  function projectButton(item) {
    const button = document.createElement("button");
    button.className = "project-row" + (ui.current?.id === item.id ? " active" : "");
    button.type = "button";
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = item.title;
    const date = document.createElement("small");
    date.textContent = "Modificado: " + item.updated_at + " · Revisión " + item.revision;
    text.append(title, date);
    const arrow = document.createElement("span");
    arrow.textContent = "›";
    button.append(text, arrow);
    button.addEventListener("click", () => openProject(item.id));
    return button;
  }
  function renderProjects() {
    const container = $("projectList");
    container.replaceChildren();
    if (!ui.projects.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Todavía no tienes proyectos. Crea el primero arriba.";
      container.append(empty);
      return;
    }
    for (const project of ui.projects) container.append(projectButton(project));
  }
  async function loadProjects() {
    const data = await request("/projects");
    ui.projects = data.projects || [];
    renderProjects();
  }
  async function openProject(id) {
    try {
      notice("");
      const { project } = await request("/projects/" + encodeURIComponent(id));
      ui.current = project;
      $("projectTitle").textContent = project.title;
      $("projectMeta").textContent = "ID: " + project.id + " · Revisión " + project.revision;
      $("recipeNotes").value = typeof project.recipe?.notes === "string" ? project.recipe.notes : "";
      $("projectDetail").hidden = false;
      renderProjects();
    } catch (error) { notice(error.message); }
  }

  $("authForm").addEventListener("submit", async event => {
    event.preventDefault();
    if (ui.busy) return;
    busy(true); notice("");
    try {
      const form = new FormData(event.currentTarget);
      const body = { email: form.get("email"), password: form.get("password") };
      const result = await request(ui.mode === "login" ? "/login" : "/register",
                                   { method: "POST", body });
      ui.csrf = result.csrf;
      event.currentTarget.elements.password.value = "";
      signedIn(true);
      await loadProjects();
      notice("Sesión de laboratorio iniciada.");
    } catch (error) { notice(error.message); }
    finally { busy(false); }
  });

  $("newProjectForm").addEventListener("submit", async event => {
    event.preventDefault();
    if (ui.busy) return;
    busy(true); notice("");
    try {
      const title = event.currentTarget.elements.title.value;
      const result = await request("/projects", { method: "POST", body: { title }, csrf: true });
      event.currentTarget.reset();
      await loadProjects();
      await openProject(result.project.id);
      notice("Proyecto guardado en el catálogo.");
    } catch (error) { notice(error.message); }
    finally { busy(false); }
  });

  $("saveNotes").addEventListener("click", async () => {
    if (ui.busy || !ui.current) return;
    busy(true); notice("");
    try {
      const updated = await request("/projects/" + encodeURIComponent(ui.current.id) + "/recipe", {
        method: "PUT",
        body: { recipe: { ...ui.current.recipe, notes: $("recipeNotes").value },
                expected_revision: ui.current.revision }, csrf: true
      });
      ui.current = updated.project;
      await loadProjects();
      $("projectMeta").textContent = "ID: " + ui.current.id + " · Revisión " + ui.current.revision;
      notice("Notas guardadas. Se recuperarán cuando vuelvas a iniciar sesión.");
    } catch (error) {
      notice(error.status === 409 ? "Otra pestaña cambió este proyecto. Vuelve a abrirlo." : error.message);
    } finally { busy(false); }
  });

  $("logoutBtn").addEventListener("click", async () => {
    if (ui.busy) return;
    busy(true); notice("");
    try {
      await request("/logout", { method: "POST", body: {}, csrf: true });
      signedIn(false);
      notice("Sesión cerrada.");
    } catch (error) { notice(error.message); }
    finally { busy(false); }
  });

  async function restore() {
    // Cookie is Secure/HttpOnly and persists after reload. Never store tokens in localStorage.
    try {
      const resumed = await request("/session/refresh", { method: "POST" });
      ui.csrf = resumed.csrf;
      signedIn(true);
      await loadProjects();
    } catch {
      signedIn(false);
    }
  }
  restore();
})();
