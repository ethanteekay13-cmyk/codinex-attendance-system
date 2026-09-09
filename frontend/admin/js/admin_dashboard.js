// Codinex Attendance System - admin dashboard logic.
const API_BASE_URL = "https://codinex-attendance-system.vercel.app/api/v1";

const ADMIN_TOKEN_KEY = "codinex_admin_token";
const ADMIN_PROFILE_KEY = "codinex_admin_profile";

function getAuthHeaders(extra = {}) {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  return { Authorization: `Bearer ${token}`, ...extra };
}

function logout() {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
  localStorage.removeItem(ADMIN_PROFILE_KEY);
  window.location.href = "login.html";
}

function showBanner(element, message, kind) {
  element.textContent = message;
  element.className = `banner is-visible banner-${kind}`;
  window.setTimeout(() => {
    element.className = "banner";
  }, 6000);
}

async function handleAuthFailure(response) {
  if (response.status === 401 || response.status === 403) {
    logout();
    return true;
  }
  return false;
}

async function loadDashboardSummary() {
  try {
    const response = await fetch(`${API_BASE_URL}/admin/dashboard-summary`, {
      headers: getAuthHeaders(),
    });
    if (await handleAuthFailure(response)) return;
    if (!response.ok) throw new Error("Could not load dashboard summary");

    const data = await response.json();
    document.getElementById("metric-present").textContent = data.present;
    document.getElementById("metric-late").textContent = data.late;
    document.getElementById("metric-absent").textContent = data.absent;
    document.getElementById("metric-total").textContent = data.total_students;

    const checkedIn = data.present + data.late;
    const percent = data.total_students > 0 ? Math.round((checkedIn / data.total_students) * 100) : 0;
    const ring = document.getElementById("summary-ring");
    ring.style.setProperty("--ring-percent", String(percent));
    document.getElementById("summary-ring-value").textContent = `${percent}%`;
  } catch (error) {
    document.getElementById("dashboard-banner").classList.add("is-visible");
  }
}

function renderStudentsTable(students) {
  const tbody = document.getElementById("students-tbody");
  const emptyState = document.getElementById("students-empty");

  if (!students.length) {
    tbody.innerHTML = "";
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";
  tbody.innerHTML = students
    .map(
      (student) => `
        <tr class="clickable-row" data-student-id="${student.student_id}">
          <td class="mono">${student.registration_number}</td>
          <td>${student.full_name}</td>
          <td>${student.university_name}</td>
          <td>${student.email}</td>
          <td>${student.phone_number}</td>
          <td><span class="status-pill status-${student.status === "active" ? "present" : "absent"}">${student.status}</span></td>
          <td class="mono">${student.attendance_percentage.toFixed(1)}%</td>
        </tr>
      `
    )
    .join("");

  tbody.querySelectorAll("tr[data-student-id]").forEach((row) => {
    row.addEventListener("click", () => openStudentDetail(row.dataset.studentId));
  });
}

async function loadStudents(searchTerm = "") {
  try {
    const url = new URL(`${API_BASE_URL}/admin/students`);
    if (searchTerm) {
      url.searchParams.set("search", searchTerm);
    }
    const response = await fetch(url, { headers: getAuthHeaders() });
    if (await handleAuthFailure(response)) return;
    if (!response.ok) throw new Error("Could not load students");

    const students = await response.json();
    renderStudentsTable(students);
  } catch (error) {
    showBanner(document.getElementById("students-banner"), "Could not load students.", "error");
  }
}

function setupSearch() {
  const input = document.getElementById("student-search");
  let debounceHandle = null;
  input.addEventListener("input", () => {
    window.clearTimeout(debounceHandle);
    debounceHandle = window.setTimeout(() => {
      loadStudents(input.value.trim());
    }, 300);
  });
}

function setupAddStudentForm() {
  const toggleButton = document.getElementById("toggle-add-student");
  const panel = document.getElementById("add-student-panel");
  const form = document.getElementById("add-student-form");
  const banner = document.getElementById("add-student-banner");

  toggleButton.addEventListener("click", () => {
    panel.style.display = panel.style.display === "none" ? "block" : "none";
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector("button[type=submit]");
    submitButton.disabled = true;
    submitButton.textContent = "Adding...";

    const payload = {
      registration_number: document.getElementById("new-registration-number").value.trim(),
      full_name: document.getElementById("new-full-name").value.trim(),
      university_name: document.getElementById("new-university-name").value.trim(),
      phone_number: document.getElementById("new-phone-number").value.trim(),
      email: document.getElementById("new-email").value.trim(),
      password: document.getElementById("new-password").value,
    };

    try {
      const response = await fetch(`${API_BASE_URL}/admin/students`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Could not add this student.", "error");
        return;
      }
      showBanner(banner, `${data.full_name} was added successfully.`, "success");
      form.reset();
      loadStudents();
      loadDashboardSummary();
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Add student";
    }
  });
}

function setupCsvImport() {
  const input = document.getElementById("csv-import-input");
  const banner = document.getElementById("import-banner");

  input.addEventListener("change", async () => {
    const file = input.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/admin/students/import`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: formData,
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Import failed.", "error");
        return;
      }
      showBanner(
        banner,
        `Import complete: ${data.created} created, ${data.failed} failed out of ${data.total_rows} rows.`,
        data.failed > 0 ? "info" : "success"
      );
      loadStudents();
      loadDashboardSummary();
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    } finally {
      input.value = "";
    }
  });
}

function setupExportReport() {
  const button = document.getElementById("export-report-btn");
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Preparing export...";
    try {
      const response = await fetch(`${API_BASE_URL}/admin/reports/export`, {
        headers: getAuthHeaders(),
      });
      if (await handleAuthFailure(response)) return;
      if (!response.ok) throw new Error("Export failed");

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = "codinex-attendance-report.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      showBanner(document.getElementById("dashboard-banner"), "Could not export the report.", "error");
    } finally {
      button.disabled = false;
      button.textContent = "Export report";
    }
  });
}

function formatDateTime(iso) {
  return new Date(iso).toLocaleString();
}

async function loadSettings() {
  const banner = document.getElementById("settings-banner");
  try {
    const response = await fetch(`${API_BASE_URL}/admin/settings`, { headers: getAuthHeaders() });
    if (await handleAuthFailure(response)) return;
    if (!response.ok) throw new Error("Could not load settings");

    const data = await response.json();
    document.getElementById("office-ips-input").value = data.office_ips.join(", ");
    document.getElementById("present-cutoff-input").value = data.present_cutoff_time;
    document.getElementById("late-cutoff-input").value = data.late_cutoff_time;
    renderOverrideStatus(data);
  } catch (error) {
    showBanner(banner, "Could not load settings.", "error");
  }
}

function renderOverrideStatus(data) {
  const statusEl = document.getElementById("override-status");
  const enableBtn = document.getElementById("enable-override-btn");
  const disableBtn = document.getElementById("disable-override-btn");

  if (data.wifi_override_enabled) {
    const until = data.wifi_override_expires_at ? formatDateTime(data.wifi_override_expires_at) : "end of day";
    statusEl.innerHTML = `<span class="status-pill status-late">Override active</span> until ${until}. Check-ins right now are accepted from any IP and flagged for review.`;
    enableBtn.style.display = "none";
    disableBtn.style.display = "inline-flex";
  } else {
    statusEl.innerHTML = `<span class="status-pill status-present">Office Wi-Fi enforced</span> - only listed IP addresses can check in.`;
    enableBtn.style.display = "inline-flex";
    disableBtn.style.display = "none";
  }
}

function setupCutoffTimesForm() {
  const form = document.getElementById("cutoff-times-form");
  const banner = document.getElementById("settings-banner");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector("button[type=submit]");
    submitButton.disabled = true;
    submitButton.textContent = "Saving...";

    const payload = {
      present_cutoff_time: document.getElementById("present-cutoff-input").value,
      late_cutoff_time: document.getElementById("late-cutoff-input").value,
    };

    try {
      const response = await fetch(`${API_BASE_URL}/admin/settings/cutoff-times`, {
        method: "PUT",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Could not save the cutoff times.", "error");
        return;
      }
      showBanner(banner, "Cutoff times updated. This takes effect immediately.", "success");
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Save cutoff times";
    }
  });
}

function setupSettingsPanel() {
  const form = document.getElementById("office-ips-form");
  const banner = document.getElementById("settings-banner");
  const enableBtn = document.getElementById("enable-override-btn");
  const disableBtn = document.getElementById("disable-override-btn");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector("button[type=submit]");
    submitButton.disabled = true;
    submitButton.textContent = "Saving...";

    const officeIps = document
      .getElementById("office-ips-input")
      .value.split(",")
      .map((ip) => ip.trim())
      .filter(Boolean);

    try {
      const response = await fetch(`${API_BASE_URL}/admin/settings/office-ips`, {
        method: "PUT",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ office_ips: officeIps }),
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Could not save the IP list.", "error");
        return;
      }
      showBanner(banner, "Office IP list updated. This takes effect immediately.", "success");
      renderOverrideStatus(data);
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Save IP addresses";
    }
  });

  enableBtn.addEventListener("click", async () => {
    if (!confirm("Allow check-in from any IP address until the end of today? This is meant for when office Wi-Fi or internet is down.")) {
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/admin/settings/wifi-override/enable`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Could not enable the override.", "error");
        return;
      }
      showBanner(banner, "Wi-Fi override enabled for the rest of today.", "info");
      renderOverrideStatus(data);
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    }
  });

  disableBtn.addEventListener("click", async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/settings/wifi-override/disable`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Could not disable the override.", "error");
        return;
      }
      showBanner(banner, "Wi-Fi override turned off. Only listed office IPs can check in now.", "success");
      renderOverrideStatus(data);
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    }
  });
}

function renderTodayAttendanceTable(rows) {
  const tbody = document.getElementById("today-attendance-tbody");
  const emptyState = document.getElementById("today-attendance-empty");

  if (!rows.length) {
    tbody.innerHTML = "";
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";
  tbody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${row.full_name}</td>
          <td class="mono">${row.registration_number}</td>
          <td class="mono">${new Date(row.check_in_time).toLocaleTimeString()}</td>
          <td><span class="status-pill status-${row.status}">${row.status}</span></td>
          <td>${row.via_wifi_override ? '<span class="status-pill status-late">Review - override used</span>' : "-"}</td>
        </tr>
      `
    )
    .join("");
}

async function loadTodayAttendance() {
  try {
    const response = await fetch(`${API_BASE_URL}/admin/attendance/today`, {
      headers: getAuthHeaders(),
    });
    if (await handleAuthFailure(response)) return;
    if (!response.ok) throw new Error("Could not load today's check-ins");

    const rows = await response.json();
    renderTodayAttendanceTable(rows);
  } catch (error) {
    showBanner(document.getElementById("today-attendance-banner"), "Could not load today's check-ins.", "error");
  }
}

// --- Weekly (Monday-Friday) grouping for attendance history tables ---

function getMondayOfWeek(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`);
  const day = d.getDay(); // 0 = Sunday ... 6 = Saturday
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diffToMonday);
  return monday;
}

function formatWeekLabel(monday) {
  const friday = new Date(monday);
  friday.setDate(monday.getDate() + 4);
  const opts = { day: "numeric", month: "short" };
  return `${monday.toLocaleDateString(undefined, opts)} - ${friday.toLocaleDateString(undefined, opts)}`;
}

function groupRecordsByWeek(records) {
  const groups = new Map();
  for (const record of records) {
    const monday = getMondayOfWeek(record.date);
    const key = monday.toISOString().slice(0, 10);
    if (!groups.has(key)) {
      groups.set(key, { monday, records: [] });
    }
    groups.get(key).records.push(record);
  }
  return Array.from(groups.values()).sort((a, b) => b.monday - a.monday);
}

function renderGroupedHistoryRows(records) {
  if (!records.length) {
    return "";
  }
  const groups = groupRecordsByWeek(records);
  return groups
    .map(
      (group) => `
        <tr class="week-group-header"><td colspan="3">Week of ${formatWeekLabel(group.monday)}</td></tr>
        ${group.records
          .map(
            (record) => `
              <tr>
                <td>${record.date}</td>
                <td class="mono">${record.check_in_time ? new Date(record.check_in_time).toLocaleTimeString() : "-"}</td>
                <td><span class="status-pill status-${record.status}">${record.status}</span></td>
              </tr>
            `
          )
          .join("")}
      `
    )
    .join("");
}

// --- Student detail modal ---

let currentDetailStudentId = null;

function openStudentDetailModal() {
  document.getElementById("student-detail-overlay").classList.add("is-visible");
}

function closeStudentDetailModal() {
  document.getElementById("student-detail-overlay").classList.remove("is-visible");
  currentDetailStudentId = null;
}

async function openStudentDetail(studentId) {
  currentDetailStudentId = studentId;
  openStudentDetailModal();

  const banner = document.getElementById("student-detail-banner");
  banner.className = "banner";
  document.getElementById("student-detail-name").textContent = "Loading...";
  document.getElementById("student-detail-history-tbody").innerHTML = "";

  try {
    const response = await fetch(`${API_BASE_URL}/admin/students/${studentId}`, {
      headers: getAuthHeaders(),
    });
    if (await handleAuthFailure(response)) return;
    if (!response.ok) throw new Error("Could not load this student's details");

    const data = await response.json();
    renderStudentDetail(data);
  } catch (error) {
    showBanner(banner, "Could not load this student's details.", "error");
  }
}

function renderStudentDetail(data) {
  const { student, history } = data;

  document.getElementById("student-detail-name").textContent = student.full_name;
  document.getElementById("student-detail-reg").textContent = student.registration_number;
  document.getElementById("student-detail-university").textContent = student.university_name;
  document.getElementById("student-detail-email").textContent = student.email;
  document.getElementById("student-detail-phone").textContent = student.phone_number;

  const percent = Math.round(history.attendance_percentage);
  const ring = document.getElementById("student-detail-ring");
  ring.style.setProperty("--ring-percent", String(percent));
  document.getElementById("student-detail-ring-value").textContent = `${percent}%`;

  document.getElementById("student-detail-present").textContent = history.total_present;
  document.getElementById("student-detail-late").textContent = history.total_late;
  document.getElementById("student-detail-absent").textContent = history.total_absent;

  const tbody = document.getElementById("student-detail-history-tbody");
  const emptyState = document.getElementById("student-detail-history-empty");
  if (!history.records.length) {
    tbody.innerHTML = "";
    emptyState.style.display = "block";
  } else {
    emptyState.style.display = "none";
    tbody.innerHTML = renderGroupedHistoryRows(history.records);
  }
}

function setupStudentDetailModal() {
  document.getElementById("student-detail-close-btn").addEventListener("click", closeStudentDetailModal);
  document.getElementById("student-detail-overlay").addEventListener("click", (event) => {
    if (event.target.id === "student-detail-overlay") {
      closeStudentDetailModal();
    }
  });

  document.getElementById("delete-history-btn").addEventListener("click", async () => {
    if (!currentDetailStudentId) return;
    if (!confirm("Delete all attendance history for this student? Their account stays active. This cannot be undone.")) {
      return;
    }
    const banner = document.getElementById("student-detail-banner");
    try {
      const response = await fetch(`${API_BASE_URL}/admin/students/${currentDetailStudentId}/history`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Could not delete history.", "error");
        return;
      }
      showBanner(banner, "Attendance history deleted.", "success");
      openStudentDetail(currentDetailStudentId);
      loadStudents();
      loadDashboardSummary();
      loadTodayAttendance();
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    }
  });

  document.getElementById("delete-student-btn").addEventListener("click", async () => {
    if (!currentDetailStudentId) return;
    if (!confirm("Permanently delete this student, including their login and all attendance history? This cannot be undone.")) {
      return;
    }
    const banner = document.getElementById("student-detail-banner");
    try {
      const response = await fetch(`${API_BASE_URL}/admin/students/${currentDetailStudentId}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Could not delete this student.", "error");
        return;
      }
      closeStudentDetailModal();
      loadStudents();
      loadDashboardSummary();
      loadTodayAttendance();
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (!localStorage.getItem(ADMIN_TOKEN_KEY)) {
    window.location.href = "login.html";
    return;
  }

  const profileRaw = localStorage.getItem(ADMIN_PROFILE_KEY);
  if (profileRaw) {
    try {
      const profile = JSON.parse(profileRaw);
      document.getElementById("admin-name").textContent = profile.full_name || "Admin";
    } catch (error) {
      document.getElementById("admin-name").textContent = "Admin";
    }
  }

  document.getElementById("logout-btn").addEventListener("click", logout);
  document.getElementById("launch-kiosk-btn").addEventListener("click", () => {
    window.open("kiosk.html", "_blank");
  });

  setupSearch();
  setupAddStudentForm();
  setupCsvImport();
  setupExportReport();
  setupSettingsPanel();
  setupCutoffTimesForm();
  setupStudentDetailModal();

  loadDashboardSummary();
  loadStudents();
  loadSettings();
  loadTodayAttendance();
});
