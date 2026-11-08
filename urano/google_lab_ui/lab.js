(() => {
  "use strict";
  const el = id => document.getElementById(id);
  let csrf = null, current = null, busy = false;
  const notice = msg => { el("notice").textContent = msg || ""; };
  function lock(value) {
    busy = value;
    for (const id of ["logout", "save"]) el(id).disabled = value;
    el("createProject").querySelector("button").disabled = value;
  }
  async function call(path, {method = "GET", body, protectedWrite = false} = {}) {
    const headers = {"Accept": "application/json"};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (protectedWrite) headers["X-Urano-CSRF"] = csrf || "";
    const response = await fetch(path, {method, credentials: "same-origin", headers,
      ...(body === undefined ? {} : {body: JSON.stringify(body)})});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(data.error || "Error HTTP " + response.status);
    return data;
  }
  function signedIn(value) {
    el("signedOut").hidden = value;
    el("signedIn").hidden = !value;
    if (!value) { csrf = null; current = null; el("detail").hidden = true; el("projects").replaceChildren(); }
  }
  async function projects() {
    const {projects: items} = await call("/urano/v1/projects");
    el("projects").replaceChildren();
    if (!items.length) {
      const p = document.createElement("p"); p.textContent = "Todavía no hay proyectos."; el("projects").append(p);
    }
    for (const item of items) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "project";
      button.textContent = item.title + " · revisión " + item.revision;
      button.setAttribute("aria-current", String(current?.id === item.id));
      button.addEventListener("click", () => openProject(item.id));
      el("projects").append(button);
    }
  }
  async function openProject(id) {
    try {
      const {project} = await call("/urano/v1/projects/" + encodeURIComponent(id));
      current = project;
      el("projectTitle").textContent = project.title;
      el("notes").value = typeof project.recipe?.notes === "string" ? project.recipe.notes : "";
      el("detail").hidden = false;
      await projects();
      notice("Proyecto recuperado.");
    } catch (err) { notice(err.message); }
  }
  el("createProject").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const title = form.elements.title.value;
    lock(true);
    try {
      const {project} = await call("/urano/v1/projects", {method:"POST", body:{title}, protectedWrite:true});
      form.reset(); await projects(); await openProject(project.id); notice("Proyecto creado.");
    } catch (err) { notice(err.message); } finally { lock(false); }
  });
  el("save").addEventListener("click", async () => {
    if (busy || !current) return;
    lock(true);
    try {
      const {project} = await call("/urano/v1/projects/" + encodeURIComponent(current.id) + "/recipe",
        {method:"PUT", body:{expected_revision:current.revision,recipe:{...current.recipe,notes:el("notes").value}}, protectedWrite:true});
      current = project; await projects(); notice("Cambios guardados.");
    } catch (err) { notice(err.message); } finally { lock(false); }
  });
  el("logout").addEventListener("click", async () => {
    if (busy) return; lock(true);
    try { await call("/urano/v1/logout", {method:"POST", body:{},protectedWrite:true}); signedIn(false); notice("Sesión cerrada."); }
    catch (err) { notice(err.message); } finally { lock(false); }
  });
  (async () => {
    try {
      const restored = await call("/urano-google-lab/session/refresh", {method:"POST"});
      csrf = restored.csrf; signedIn(true); await projects();
    } catch (err) { signedIn(false); }
  })();
})();