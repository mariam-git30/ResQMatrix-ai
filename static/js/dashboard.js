(() => {
  const state = { emergencies: [], resources: [], history: [], priorities: [] };
  const emergencyModalElement = document.querySelector("#emergencyModal");
  const resourceModalElement = document.querySelector("#resourceModal");
  const priorityModalElement = document.querySelector("#priorityModal");
  const emergencyModal = emergencyModalElement && window.bootstrap
    ? bootstrap.Modal.getOrCreateInstance(emergencyModalElement)
    : null;
  const resourceModal = resourceModalElement && window.bootstrap
    ? bootstrap.Modal.getOrCreateInstance(resourceModalElement)
    : null;
  const priorityModal = priorityModalElement && window.bootstrap
    ? bootstrap.Modal.getOrCreateInstance(priorityModalElement)
    : null;

  const $ = (selector) => document.querySelector(selector);

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function label(value) {
    return String(value ?? "")
      .toLowerCase()
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function formatDate(value) {
    if (!value) return "Time not recorded";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function numberValue(id) {
    const value = $(id)?.value.trim();
    return value === "" ? null : Number(value);
  }

  function setText(selector, value) {
    const element = $(selector);
    if (element) element.textContent = value;
  }

  async function request(url, options = {}) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...options,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const details = body.errors
        ? Object.values(body.errors).join(" ")
        : body.message || "Request failed.";
      throw new Error(details);
    }
    return body;
  }

  async function loadDashboard() {
    try {
      const [stats, emergencyResponse, resourceResponse, historyResponse, priorityResponse] =
        await Promise.all([
          request("/api/dashboard/stats"),
          request("/api/emergencies"),
          request("/api/resources"),
          request("/api/history"),
          request("/api/priority/emergencies"),
        ]);
      state.emergencies = emergencyResponse.data;
      state.resources = resourceResponse.data;
      state.history = historyResponse.data;
      state.priorities = priorityResponse.data;
      renderStats(stats.data);
      renderPriorities();
      renderEmergencies();
      renderResources();
      renderHistory();
    } catch (error) {
      showPageError(error.message);
    }
  }

  function renderStats(stats) {
    setText("#activeIncidentCount", stats.active_incidents);
    setText("#availableResourceCount", stats.available_resources);
    setText("#responseActionCount", stats.response_actions_today);
    setText("#incidentNavCount", String(stats.active_incidents).padStart(2, "0"));
    setText("#resourceNavCount", String(stats.total_resources).padStart(2, "0"));
    setText("#databaseReadiness", "READY");
  }

  function renderEmergencies() {
    const container = $("#incidentList");
    if (!container) return;
    if (!state.emergencies.length) {
      container.innerHTML = `
        <div class="empty-state compact-empty">
          <div class="empty-illustration" aria-hidden="true"><span>+</span></div>
          <h3>No emergencies recorded</h3>
          <p>Create an emergency record to begin tracking the response queue.</p>
        </div>`;
      return;
    }
    container.innerHTML = state.emergencies.map((item) => {
      const priority = priorityFor(item.id);
      return `
      <article class="incident-item">
        <div class="incident-severity severity-${severityTone(item.severity)}">
          <strong>${escapeHtml(item.severity)}</strong><small>SEV</small>
        </div>
        <div class="incident-main">
          <div class="incident-title-row">
            <h3>${escapeHtml(item.title)}</h3>
            <span class="status-pill status-${item.status.toLowerCase()}">${escapeHtml(label(item.status))}</span>
          </div>
          <div class="incident-meta">
            <span>${escapeHtml(label(item.type))}</span>
            <span>${escapeHtml(item.location)}</span>
            <span>${escapeHtml(formatDate(item.reported_time || item.created_at))}</span>
          </div>
          <div class="incident-facts">
            <span><b>${item.people_affected}</b> affected</span>
            <span><b>${item.injured}</b> injured</span>
            <span><b>${item.critical_injured}</b> critical</span>
            <span><b>${item.urgency}</b> urgency</span>
            <span class="incident-priority-fact"><b>${priority ? priority.priority_score.toFixed(2) : "—"}</b> priority</span>
          </div>
        </div>
        <div class="item-actions">
          ${priority ? `<button class="item-action analyze-priority" type="button" data-id="${item.id}">Analyze priority</button><button class="item-action why-priority" type="button" data-id="${item.id}">Why?</button>` : ""}
          <button class="item-action edit-emergency" type="button" data-id="${item.id}">Edit</button>
          <button class="item-action delete-emergency" type="button" data-id="${item.id}">Delete</button>
        </div>
      </article>`;
    }).join("");
    container.querySelectorAll(".analyze-priority, .why-priority").forEach((button) => {
      button.addEventListener("click", () => showPriority(Number(button.dataset.id)));
    });
    container.querySelectorAll(".edit-emergency").forEach((button) => {
      button.addEventListener("click", () => openEmergencyEditor(Number(button.dataset.id)));
    });
    container.querySelectorAll(".delete-emergency").forEach((button) => {
      button.addEventListener("click", () => deleteRecord("emergencies", Number(button.dataset.id)));
    });
  }

  function priorityFor(id) {
    return state.priorities.find((item) => item.emergency_id === id);
  }

  function priorityLevelClass(level) {
    return `priority-level-${String(level || "LOW").toLowerCase()}`;
  }

  function renderPriorities() {
    const container = $("#priorityList");
    if (!container) return;
    if (!state.priorities.length) {
      container.innerHTML = `
        <div class="empty-state compact-empty">
          <div class="empty-illustration" aria-hidden="true">⌁</div>
          <h3>No active priorities</h3>
          <p>Only active and in-progress emergencies are analyzed by the local engine.</p>
        </div>`;
      return;
    }
    container.innerHTML = `
      <div class="priority-table-scroll">
        <table class="priority-table">
          <thead><tr>
            <th>Priority</th><th>Emergency</th><th>Type</th><th>Location</th>
            <th>Severity</th><th>Critical injuries</th><th>People affected</th>
            <th>Urgency</th><th>Priority score</th><th>Level</th><th>Why?</th>
          </tr></thead>
          <tbody>${state.priorities.map((priority) => {
            const emergency = state.emergencies.find((item) => item.id === priority.emergency_id);
            if (!emergency) return "";
            return `
              <tr>
                <td><span class="priority-rank">#${state.priorities.indexOf(priority) + 1}</span></td>
                <td><strong>${escapeHtml(emergency.title)}</strong></td>
                <td>${escapeHtml(label(emergency.type))}</td>
                <td>${escapeHtml(emergency.location)}</td>
                <td>${emergency.severity}</td>
                <td>${emergency.critical_injured}</td>
                <td>${emergency.people_affected}</td>
                <td>${emergency.urgency}</td>
                <td><strong class="priority-score">${priority.priority_score.toFixed(2)}</strong></td>
                <td><span class="priority-level ${priorityLevelClass(priority.priority_level)}">${escapeHtml(priority.priority_level)}</span></td>
                <td><button class="item-action why-priority" type="button" data-id="${emergency.id}">Why?</button></td>
              </tr>`;
          }).join("")}</tbody>
        </table>
      </div>`;
    container.querySelectorAll(".why-priority").forEach((button) => {
      button.addEventListener("click", () => showPriority(Number(button.dataset.id)));
    });
  }

  async function showPriority(id) {
    if (!priorityModal) return;
    const body = $("#priorityModalBody");
    const emergency = state.emergencies.find((item) => item.id === id);
    if (!body || !emergency) return;
    body.innerHTML = `<div class="loading-state">Calculating priority analysis…</div>`;
    priorityModal.show();
    try {
      const response = await request("/api/priority/calculate", {
        method: "POST",
        body: JSON.stringify({ emergency_id: id }),
      });
      const priority = response.data;
      body.innerHTML = `
        <div class="priority-analysis-heading">
          <div>
            <span class="panel-kicker">${escapeHtml(label(emergency.type))} / ${escapeHtml(emergency.location)}</span>
            <h3>${escapeHtml(emergency.title)}</h3>
          </div>
          <div class="priority-analysis-score">
            <strong>${priority.priority_score.toFixed(2)}</strong>
            <span>/ 100</span>
            <b class="priority-level ${priorityLevelClass(priority.priority_level)}">${escapeHtml(priority.priority_level)}</b>
          </div>
        </div>
        <div class="priority-explanation">${escapeHtml(priority.explanation)}</div>
        <div class="priority-top-factors">
          <span class="panel-kicker">TOP CONTRIBUTING FACTORS</span>
          <div>${priority.top_factors.map((factor) => `
            <span class="top-factor-chip">${escapeHtml(factor.label)} <b>${factor.weighted_contribution.toFixed(2)}</b></span>
          `).join("")}</div>
        </div>
        <div class="factor-list">
          ${Object.entries(priority.factors).map(([factor, score]) => `
            <div class="factor-row">
              <div class="factor-label"><span>${escapeHtml(label(factor))}</span><b>${Number(score).toFixed(0)}/100</b></div>
              <div class="factor-track"><span style="width: ${Math.max(0, Math.min(100, Number(score)))}%"></span></div>
              <small>Weight ${Number(priority.weights[factor] * 100).toFixed(0)}%</small>
            </div>
          `).join("")}
        </div>`;
    } catch (error) {
      body.innerHTML = `<div class="inline-error">${escapeHtml(error.message)}</div>`;
    }
  }

  async function recalculatePriorities() {
    const button = $("#recalculatePriorities");
    if (button) {
      button.disabled = true;
      button.textContent = "Recalculating…";
    }
    try {
      const response = await request("/api/priority/emergencies");
      state.priorities = response.data;
      renderPriorities();
      renderEmergencies();
    } catch (error) {
      showPageError(error.message);
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = "Recalculate priorities";
      }
    }
  }

  function severityTone(score) {
    if (score >= 80) return "critical";
    if (score >= 50) return "elevated";
    return "routine";
  }

  function renderResources() {
    const container = $("#resourceList");
    if (!container) return;
    if (!state.resources.length) {
      container.innerHTML = `<div class="empty-state compact-empty"><h3>No resources recorded</h3><p>Add a resource to begin tracking field readiness.</p></div>`;
      return;
    }
    container.innerHTML = state.resources.map((item) => `
      <div class="resource-row resource-row-managed">
        <span class="resource-mark resource-mark-${resourceTone(item.status)}"></span>
        <div>
          <strong>${escapeHtml(item.name)}</strong>
          <small>${escapeHtml(label(item.type))} · ${escapeHtml(item.location)}</small>
        </div>
        <div class="resource-quantity"><b>${item.available_quantity}</b> / ${item.quantity}</div>
        <span class="status-pill status-${item.status.toLowerCase()}">${escapeHtml(label(item.status))}</span>
        <div class="item-actions resource-actions">
          <button class="item-action edit-resource" type="button" data-id="${item.id}">Edit</button>
          <button class="item-action delete-resource" type="button" data-id="${item.id}">Delete</button>
        </div>
      </div>`).join("");
    container.querySelectorAll(".edit-resource").forEach((button) => {
      button.addEventListener("click", () => openResourceEditor(Number(button.dataset.id)));
    });
    container.querySelectorAll(".delete-resource").forEach((button) => {
      button.addEventListener("click", () => deleteRecord("resources", Number(button.dataset.id)));
    });
  }

  function resourceTone(status) {
    if (status === "AVAILABLE") return "green";
    if (status === "PARTIALLY_AVAILABLE") return "blue";
    if (status === "DEPLOYED") return "orange";
    return "muted";
  }

  function renderHistory() {
    const container = $("#activityList");
    if (!container) return;
    if (!state.history.length) {
      container.innerHTML = `<div class="activity-empty"><span class="activity-line"></span><p>No response actions recorded yet.</p></div>`;
      return;
    }
    container.innerHTML = state.history.slice(0, 5).map((entry) => {
      const subject = entry.emergency_title || entry.resource_name || "Workspace";
      return `
        <div class="activity-row">
          <span class="activity-dot"></span>
          <div><strong>${escapeHtml(label(entry.action))}</strong><span>${escapeHtml(subject)}</span></div>
          <time>${escapeHtml(formatDate(entry.timestamp))}</time>
        </div>`;
    }).join("");
  }

  function showPageError(message) {
    setText("#apiStatus", "DATA ERROR");
    const banner = $(".status-banner");
    if (banner) banner.classList.add("status-banner-error");
    const list = $("#incidentList");
    if (list) list.innerHTML = `<div class="inline-error">${escapeHtml(message)}</div>`;
  }

  function resetForm(form, errorSelector) {
    form.reset();
    form.querySelectorAll("input[type=hidden]").forEach((input) => { input.value = ""; });
    const error = $(errorSelector);
    if (error) error.textContent = "";
  }

  function openEmergencyEditor(id = null) {
    const form = $("#emergencyForm");
    if (!form || !emergencyModal) return;
    resetForm(form, "#emergencyFormError");
    const record = state.emergencies.find((item) => item.id === id);
    setText("#emergencyModalTitle", record ? "Edit emergency" : "New emergency");
    if (record) {
      $("#emergencyId").value = record.id;
      $("#emergencyTitle").value = record.title;
      $("#emergencyType").value = record.type;
      $("#emergencyStatus").value = record.status;
      $("#emergencyLocation").value = record.location;
      $("#emergencyDescription").value = record.description || "";
      $("#emergencySeverity").value = record.severity;
      $("#emergencyUrgency").value = record.urgency;
      $("#peopleAffected").value = record.people_affected;
      $("#injured").value = record.injured;
      $("#criticalInjured").value = record.critical_injured;
      $("#reportedTime").value = toLocalInputValue(record.reported_time);
      $("#emergencyLatitude").value = record.latitude ?? "";
      $("#emergencyLongitude").value = record.longitude ?? "";
    } else {
      $("#emergencyStatus").value = "ACTIVE";
      $("#emergencySeverity").value = 50;
      $("#emergencyUrgency").value = 50;
      $("#reportedTime").value = toLocalInputValue(new Date().toISOString());
    }
    emergencyModal.show();
  }

  function openResourceEditor(id = null) {
    const form = $("#resourceForm");
    if (!form || !resourceModal) return;
    resetForm(form, "#resourceFormError");
    const record = state.resources.find((item) => item.id === id);
    setText("#resourceModalTitle", record ? "Edit resource" : "Add resource");
    if (record) {
      $("#resourceId").value = record.id;
      $("#resourceName").value = record.name;
      $("#resourceType").value = record.type;
      $("#resourceStatus").value = record.status;
      $("#resourceLocation").value = record.location;
      $("#resourceDescription").value = record.description || "";
      $("#resourceQuantity").value = record.quantity;
      $("#availableQuantity").value = record.available_quantity;
      $("#resourceCapacity").value = record.capacity ?? "";
      $("#resourceLatitude").value = record.latitude ?? "";
      $("#resourceLongitude").value = record.longitude ?? "";
    } else {
      $("#resourceStatus").value = "AVAILABLE";
      $("#resourceQuantity").value = 1;
      $("#availableQuantity").value = 1;
    }
    resourceModal.show();
  }

  function toLocalInputValue(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const pad = (number) => String(number).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  function collectForm(form) {
    const data = {};
    new FormData(form).forEach((value, key) => {
      if (key !== "id") data[key] = value;
    });
    ["severity", "urgency", "people_affected", "injured", "critical_injured", "latitude", "longitude", "quantity", "available_quantity", "capacity"].forEach((field) => {
      if (field in data) data[field] = data[field] === "" ? null : Number(data[field]);
    });
    return data;
  }

  async function saveForm(form, endpoint, idSelector, errorSelector, modal) {
    const id = $(idSelector)?.value;
    const method = id ? "PUT" : "POST";
    try {
      await request(`${endpoint}${id ? `/${id}` : ""}`, { method, body: JSON.stringify(collectForm(form)) });
      modal.hide();
      await loadDashboard();
    } catch (error) {
      const errorElement = $(errorSelector);
      if (errorElement) errorElement.textContent = error.message;
    }
  }

  async function deleteRecord(collection, id) {
    if (!window.confirm("Remove this record from the workspace?")) return;
    try {
      await request(`/api/${collection}/${id}`, { method: "DELETE" });
      await loadDashboard();
    } catch (error) {
      window.alert(error.message);
    }
  }

  function updateClock() {
    const currentTime = $("#currentTime");
    const currentDate = $("#currentDate");
    if (!currentTime || !currentDate) return;
    const now = new Date();
    currentDate.textContent = new Intl.DateTimeFormat("en-GB", {
      day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Kolkata",
    }).format(now).toUpperCase();
    currentTime.textContent = `${new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZone: "Asia/Kolkata",
    }).format(now)} IST`;
  }

  async function checkHealth() {
    const apiStatus = $("#apiStatus");
    const healthReadiness = $("#healthReadiness");
    if (!apiStatus || !healthReadiness) return;
    try {
      const health = await request("/api/health");
      apiStatus.textContent = health.status === "success" ? "API ONLINE" : "API REVIEW";
      healthReadiness.textContent = "READY";
    } catch (_error) {
      apiStatus.textContent = "API OFFLINE";
      healthReadiness.textContent = "REVIEW";
      healthReadiness.style.color = "#c55f5f";
    }
  }

  const mobileToggle = $(".mobile-nav-toggle");
  const dashboardNav = $("#dashboardNav");
  if (mobileToggle && dashboardNav) {
    mobileToggle.addEventListener("click", () => {
      const isOpen = dashboardNav.classList.toggle("is-open");
      mobileToggle.setAttribute("aria-expanded", String(isOpen));
    });
  }

  $("#openEmergencyModal")?.addEventListener("click", () => openEmergencyEditor());
  $("#openResourceModal")?.addEventListener("click", () => openResourceEditor());
  $("#recalculatePriorities")?.addEventListener("click", recalculatePriorities);
  $("#emergencyForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    saveForm(event.currentTarget, "/api/emergencies", "#emergencyId", "#emergencyFormError", emergencyModal);
  });
  $("#resourceForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    saveForm(event.currentTarget, "/api/resources", "#resourceId", "#resourceFormError", resourceModal);
  });

  updateClock();
  window.setInterval(updateClock, 1000);
  checkHealth();
  loadDashboard();

  // Steps 4B–8: optimization, human review, map, simulation, analytics.
  state.allocations = [];
  state.optimization = null;

  function priorityLevelForEmergency(id) {
    const p = priorityFor(id);
    return p ? p.priority_level : "LOW";
  }

  function renderAllocationMetrics() {
    const recommendations = state.allocations.filter(a => a.status === "RECOMMENDED").length;
    const approved = state.allocations.filter(a => a.status === "APPROVED").length;
    const unfulfilled = state.optimization?.unfulfilled_demand?.length || 0;
    setText("#allocationCount", recommendations);
    setText("#approvedCount", approved);
    setText("#unfulfilledCount", unfulfilled);
    setText("#liveAvailableCount", state.resources.reduce((sum,r)=>sum+Number(r.available_quantity||0),0));
  }

  function renderAllocations() {
    const container=$("#allocationList"); if(!container) return;
    const priorityFilter=$("#allocationPriorityFilter")?.value || "";
    const typeFilter=$("#allocationTypeFilter")?.value || "";
    const statusFilter=$("#allocationStatusFilter")?.value || "";
    const rows=state.allocations.filter(a => (!priorityFilter || priorityLevelForEmergency(a.emergency_id)===priorityFilter) && (!typeFilter || a.resource_type===typeFilter) && (!statusFilter || a.status===statusFilter));
    if(!rows.length){container.innerHTML='<div class="empty-state compact-empty"><h3>No allocation records match</h3><p>Run optimization or adjust the filters.</p></div>';return;}
    container.innerHTML=`<table class="allocation-table"><thead><tr><th>Emergency</th><th>Resource</th><th>Qty</th><th>Priority</th><th>Match</th><th>Distance / ETA</th><th>Status</th><th>Reason</th><th>Action</th></tr></thead><tbody>${rows.map(a=>`
      <tr><td><strong>${escapeHtml(a.emergency_title||("Emergency #"+a.emergency_id))}</strong><br><span class="review-meta">${escapeHtml(label(priorityLevelForEmergency(a.emergency_id)))}</span></td>
      <td>${escapeHtml(a.resource_name||("Resource #"+a.resource_id))}<br><span class="review-meta">${escapeHtml(label(a.resource_type))}</span></td><td><strong>${a.quantity}</strong></td><td>${Number(a.priority_score||0).toFixed(2)}</td><td class="match-score">${Number(a.match_score||0).toFixed(2)}</td><td>${a.distance_km==null?'—':Number(a.distance_km).toFixed(1)+' km'}<br><span class="review-meta">${a.eta_minutes==null?'ETA unavailable':Number(a.eta_minutes).toFixed(1)+' min est.'}</span></td>
      <td><span class="status-pill status-${String(a.status).toLowerCase()}">${escapeHtml(label(a.status))}</span></td><td class="allocation-reason">${escapeHtml(a.allocation_reason||'')}</td>
      <td class="allocation-actions">${a.status==='RECOMMENDED'?`<button class="btn btn-sm btn-outline-secondary approve-allocation" data-id="${a.id||a.allocation_id}">Approve</button><button class="btn btn-sm btn-outline-secondary reject-allocation" data-id="${a.id||a.allocation_id}">Reject</button>`:'—'}</td></tr>`).join('')}</tbody></table>`;
    container.querySelectorAll('.approve-allocation').forEach(b=>b.addEventListener('click',()=>decideAllocation(Number(b.dataset.id),'approve')));
    container.querySelectorAll('.reject-allocation').forEach(b=>b.addEventListener('click',()=>decideAllocation(Number(b.dataset.id),'reject')));
  }

  async function loadAllocations(){
    try{ const r=await request('/api/allocations'); state.allocations=r.data||[]; renderAllocationMetrics(); renderAllocations(); renderReview(); }
    catch(e){ const c=$("#allocationList"); if(c)c.innerHTML=`<div class="inline-error">${escapeHtml(e.message)}</div>`; }
  }

  async function runOptimization(){
    const b=$("#runOptimization"); if(b){b.disabled=true;b.textContent='Optimizing…';}
    try{const r=await request('/api/optimize',{method:'POST',body:JSON.stringify({})});state.optimization=r.data;state.allocations=r.data.recommendations||[];renderAllocationMetrics();renderAllocations();renderReview();const w=$("#allocationWarning");if(w){const list=r.data.unfulfilled_demand||[];w.classList.toggle('d-none',!list.length);w.innerHTML=list.length?`<strong>Resource constrained:</strong> ${list.length} emergency/emergencies have unmet demand. The optimizer did not exceed available quantities.`:'';} await loadDashboard(); await loadAllocations();}
    catch(e){window.alert(e.message)}finally{if(b){b.disabled=false;b.innerHTML='Run AI optimization <span>↗</span>';}}
  }

  async function decideAllocation(id, action){
    if(!id)return;
    if(action==='approve' && !window.confirm('Approve this recommendation and deploy the listed quantity?')) return;
    try{await request(`/api/allocations/${id}/${action}`,{method:'POST',body:JSON.stringify({})});await loadDashboard();await loadAllocations();}
    catch(e){window.alert(e.message)}
  }

  function renderReview(){
    const c=$("#reviewList");if(!c)return;
    const rows=state.allocations.filter(a=>a.status==='RECOMMENDED').slice(0,8);
    if(!rows.length){c.innerHTML='<div class="empty-state compact-empty"><h3>No pending recommendations</h3><p>Run optimization to create recommendations for operator review.</p></div>';return;}
    c.innerHTML=rows.map(a=>`<article class="review-card"><span class="review-meta">${escapeHtml(label(a.resource_type))} · ${Number(a.eta_minutes||0).toFixed(1)} min est.</span><h3>${escapeHtml(a.emergency_title||'Emergency')}</h3><p>Recommend <strong>${a.quantity}</strong> × ${escapeHtml(a.resource_name||'resource')} because priority is ${Number(a.priority_score||0).toFixed(2)}/100 and match score is ${Number(a.match_score||0).toFixed(2)}/100.</p><div class="review-buttons"><button class="btn btn-primary btn-sm approve-allocation" data-id="${a.id||a.allocation_id}">Approve</button><button class="btn btn-outline-secondary btn-sm reject-allocation" data-id="${a.id||a.allocation_id}">Reject</button></div></article>`).join('');
    c.querySelectorAll('.approve-allocation').forEach(b=>b.addEventListener('click',()=>decideAllocation(Number(b.dataset.id),'approve')));
    c.querySelectorAll('.reject-allocation').forEach(b=>b.addEventListener('click',()=>decideAllocation(Number(b.dataset.id),'reject')));
  }

  function initResqMap(){
    const el=$("#resqMap");if(!el||!window.L)return;
    const map=L.map(el).setView([20.5937,78.9629],5);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors'}).addTo(map);
    const markers=[];
    state.emergencies.forEach(e=>{if(e.latitude==null||e.longitude==null)return;const m=L.marker([e.latitude,e.longitude]).addTo(map);m.bindPopup(`<strong>Emergency</strong><br>${escapeHtml(e.title)}<br>Priority: ${Number(priorityFor(e.id)?.priority_score||0).toFixed(2)}`);markers.push(m);});
    state.resources.forEach(r=>{if(r.latitude==null||r.longitude==null)return;const m=L.circleMarker([r.latitude,r.longitude],{radius:7}).addTo(map);m.bindPopup(`<strong>Resource</strong><br>${escapeHtml(r.name)}<br>Available: ${r.available_quantity}/${r.quantity}`);markers.push(m);});
    if(markers.length)map.fitBounds(L.featureGroup(markers).getBounds().pad(.15));
    window.setTimeout(()=>map.invalidateSize(),300);
  }

  async function runSimulation(){
    const value=Number($("#resourceReduction")?.value||20);setText('#resourceReductionValue',`${value}%`);const out=$("#simulationResult");if(out)out.innerHTML='<div class="loading-state">Running non-persistent scenario…</div>';
    try{const r=await request('/api/simulation/run',{method:'POST',body:JSON.stringify({resource_reduction_percent:value})});const d=r.data;if(out)out.innerHTML=`<div class="sim-grid"><article><span>BASELINE RECOMMENDATIONS</span><strong>${d.baseline.recommendation_count}</strong></article><article><span>SCENARIO RECOMMENDATIONS</span><strong>${d.what_if.recommendation_count}</strong></article><article><span>SCENARIO UNFULFILLED</span><strong>${d.what_if.unfulfilled_count}</strong></article></div><p class="muted-copy" style="margin-top:12px">At ${value}% simulated reduction, the optimizer recomputed allocations without writing the scenario to SQLite.</p>`;}
    catch(e){if(out)out.innerHTML=`<div class="inline-error">${escapeHtml(e.message)}</div>`}
  }

  async function loadAnalytics(){
    const c=$("#analyticsGrid");if(!c)return;try{const r=await request('/api/analytics');const d=r.data;const maxType=Math.max(1,...d.emergencies_by_type.map(x=>x.count));const maxStatus=Math.max(1,...d.allocation_status.map(x=>x.count));c.innerHTML=`<article class="analytics-card"><h3>Emergency mix</h3>${d.emergencies_by_type.map(x=>`<div class="bar-row"><div><div class="bar-label">${escapeHtml(label(x.type))}</div><div class="bar-track"><div class="bar-fill" style="width:${x.count/maxType*100}%"></div></div></div><div class="bar-value">${x.count}</div></div>`).join('')}</article><article class="analytics-card"><h3>Allocation outcomes</h3>${d.allocation_status.length?d.allocation_status.map(x=>`<div class="bar-row"><div><div class="bar-label">${escapeHtml(label(x.status))}</div><div class="bar-track"><div class="bar-fill" style="width:${x.count/maxStatus*100}%"></div></div></div><div class="bar-value">${x.count}</div></div>`).join(''):'<p class="muted-copy">No allocation decisions yet.</p>'}</article><article class="analytics-card"><h3>Decision summary</h3><div class="bar-row"><div class="bar-label">Active / in progress</div><div class="bar-value">${d.emergencies.active}</div></div><div class="bar-row"><div class="bar-label">Resolved</div><div class="bar-value">${d.emergencies.resolved}</div></div><div class="bar-row"><div class="bar-label">Approved</div><div class="bar-value">${d.allocations.approved}</div></div><div class="bar-row"><div class="bar-label">Rejected</div><div class="bar-value">${d.allocations.rejected}</div></div></article>`;}
    catch(e){c.innerHTML=`<div class="inline-error">${escapeHtml(e.message)}</div>`}
  }

  $("#runOptimization")?.addEventListener('click',runOptimization);
  $("#refreshAllocations")?.addEventListener('click',loadAllocations);
  document.querySelectorAll("#allocationPriorityFilter,#allocationTypeFilter,#allocationStatusFilter").forEach(el => el.addEventListener('change', renderAllocations));
  $("#runSimulation")?.addEventListener('click',runSimulation);
  $("#resourceReduction")?.addEventListener('input',e=>setText('#resourceReductionValue',`${e.target.value}%`));
  $("#refreshAnalytics")?.addEventListener('click',loadAnalytics);
  const allocationTypeFilter=$("#allocationTypeFilter");
  if(allocationTypeFilter){[...new Set(state.resources.map(r=>r.type))].sort().forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=label(t);allocationTypeFilter.appendChild(o);});}
  loadAllocations();loadAnalytics();
  window.setTimeout(initResqMap,900);

})();