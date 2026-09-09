// Codinex Attendance System - student dashboard logic.
const API_BASE_URL = "https://codinex-attendance-system.vercel.app/api/v1";

const STUDENT_TOKEN_KEY = "codinex_student_token";
const STUDENT_PROFILE_KEY = "codinex_student_profile";

function getAuthHeaders(extra = {}) {
  const token = localStorage.getItem(STUDENT_TOKEN_KEY);
  return { Authorization: `Bearer ${token}`, ...extra };
}

function logout() {
  localStorage.removeItem(STUDENT_TOKEN_KEY);
  localStorage.removeItem(STUDENT_PROFILE_KEY);
  window.location.href = "login.html";
}

async function handleAuthFailure(response) {
  if (response.status === 401 || response.status === 403) {
    logout();
    return true;
  }
  return false;
}

function renderProfile(profile) {
  document.getElementById("student-name").textContent = profile.full_name;
  document.getElementById("profile-registration-number").textContent = profile.registration_number;
  document.getElementById("profile-university").textContent = profile.university_name;
  document.getElementById("profile-email").textContent = profile.email;
  document.getElementById("profile-phone").textContent = profile.phone_number;
}

function renderHistory(history) {
  const ring = document.getElementById("attendance-ring");
  const percent = Math.round(history.attendance_percentage);
  ring.style.setProperty("--ring-percent", String(percent));
  document.getElementById("attendance-ring-value").textContent = `${percent}%`;

  document.getElementById("stat-present").textContent = history.total_present;
  document.getElementById("stat-late").textContent = history.total_late;
  document.getElementById("stat-absent").textContent = history.total_absent;

  const tbody = document.getElementById("history-tbody");
  const emptyState = document.getElementById("history-empty");

  if (!history.records.length) {
    tbody.innerHTML = "";
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";
  tbody.innerHTML = history.records
    .map((record) => {
      const checkInTime = record.check_in_time
        ? new Date(record.check_in_time).toLocaleTimeString()
        : "--";
      return `
        <tr>
          <td>${record.date}</td>
          <td class="mono">${checkInTime}</td>
          <td><span class="status-pill status-${record.status}">${record.status}</span></td>
        </tr>
      `;
    })
    .join("");
}

async function loadDashboard() {
  const banner = document.getElementById("dashboard-banner");
  try {
    const [profileResponse, historyResponse] = await Promise.all([
      fetch(`${API_BASE_URL}/students/me`, { headers: getAuthHeaders() }),
      fetch(`${API_BASE_URL}/students/me/history`, { headers: getAuthHeaders() }),
    ]);

    if (await handleAuthFailure(profileResponse)) return;
    if (await handleAuthFailure(historyResponse)) return;

    if (!profileResponse.ok || !historyResponse.ok) {
      throw new Error("Could not load dashboard data");
    }

    const profile = await profileResponse.json();
    const history = await historyResponse.json();

    localStorage.setItem(STUDENT_PROFILE_KEY, JSON.stringify(profile));
    renderProfile(profile);
    renderHistory(history);
  } catch (error) {
    banner.classList.add("is-visible");
  }
}

function setupChangePasswordForm() {
  const form = document.getElementById("change-password-form");
  const banner = document.getElementById("change-password-banner");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const currentPassword = document.getElementById("current-password").value;
    const newPassword = document.getElementById("new-password").value;
    const confirmPassword = document.getElementById("confirm-new-password").value;

    if (newPassword !== confirmPassword) {
      showBanner(banner, "New password and confirmation do not match.", "error");
      return;
    }
    if (newPassword.length < 8) {
      showBanner(banner, "New password must be at least 8 characters.", "error");
      return;
    }

    const submitButton = form.querySelector("button[type=submit]");
    submitButton.disabled = true;
    submitButton.textContent = "Updating...";

    try {
      const response = await fetch(`${API_BASE_URL}/students/me/change-password`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      const data = await response.json();
      if (await handleAuthFailure(response)) return;
      if (!response.ok) {
        showBanner(banner, data.detail || "Could not update your password.", "error");
        return;
      }
      showBanner(banner, "Password updated. Use your new password next time you sign in.", "success");
      form.reset();
    } catch (error) {
      showBanner(banner, "Could not reach the server. Please try again.", "error");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Update password";
    }
  });
}

function showBanner(element, message, kind) {
  element.textContent = message;
  element.className = `banner is-visible banner-${kind}`;
  window.setTimeout(() => {
    element.className = "banner";
  }, 6000);
}

document.addEventListener("DOMContentLoaded", () => {
  if (!localStorage.getItem(STUDENT_TOKEN_KEY)) {
    window.location.href = "login.html";
    return;
  }

  setupChangePasswordForm();

  document.getElementById("logout-btn").addEventListener("click", logout);
  loadDashboard();
});
