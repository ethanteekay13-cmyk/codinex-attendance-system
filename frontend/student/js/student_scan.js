// Codinex Attendance System - student scan/check-in logic.
const API_BASE_URL = "https://codinex-attendance-system.vercel.app/api/v1";

const STUDENT_TOKEN_KEY = "codinex_student_token";

function setView(state) {
  const views = ["loading", "success", "error", "no-token"];
  views.forEach((name) => {
    const el = document.getElementById(`view-${name}`);
    el.style.display = name === state ? "flex" : "none";
  });
}

async function submitCheckIn(token) {
  const studentToken = localStorage.getItem(STUDENT_TOKEN_KEY);

  try {
    const response = await fetch(`${API_BASE_URL}/attendance/check-in`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${studentToken}`,
      },
      body: JSON.stringify({ token }),
    });

    const data = await response.json();

    if (response.status === 401) {
      // The stored session is no longer valid; send the student back
      // through login and preserve the scan token for a retry.
      localStorage.removeItem(STUDENT_TOKEN_KEY);
      window.location.href = `login.html?redirect=scan&token=${encodeURIComponent(token)}`;
      return;
    }

    if (!response.ok) {
      document.getElementById("error-message").textContent =
        data.detail || "Could not record your check-in. Please try again.";
      setView("error");
      return;
    }

    document.getElementById("success-status").textContent = data.status;
    document.getElementById("success-status").className = `status-pill status-${data.status}`;
    document.getElementById("success-time").textContent = new Date(
      data.check_in_time
    ).toLocaleTimeString();
    setView("success");
  } catch (error) {
    document.getElementById("error-message").textContent =
      "Could not reach the server. Check your connection and try again.";
    setView("error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");

  if (!token) {
    setView("no-token");
    return;
  }

  if (!localStorage.getItem(STUDENT_TOKEN_KEY)) {
    window.location.href = `login.html?redirect=scan&token=${encodeURIComponent(token)}`;
    return;
  }

  setView("loading");
  submitCheckIn(token);

  document.getElementById("retry-btn").addEventListener("click", () => {
    setView("loading");
    submitCheckIn(token);
  });
});
