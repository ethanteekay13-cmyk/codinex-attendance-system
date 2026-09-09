// Codinex Attendance System - admin login logic.
// Update this constant if the backend is deployed somewhere other than
// localhost during development.
const API_BASE_URL = "https://codinex-attendance-system.vercel.app/api/v1";

const ADMIN_TOKEN_KEY = "codinex_admin_token";
const ADMIN_PROFILE_KEY = "codinex_admin_profile";

function showBanner(element, message, kind) {
  element.textContent = message;
  element.className = `banner is-visible banner-${kind}`;
}

function hideBanner(element) {
  element.className = "banner";
  element.textContent = "";
}

function setLoading(button, isLoading, defaultLabel) {
  button.disabled = isLoading;
  button.textContent = isLoading ? "Signing in..." : defaultLabel;
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("admin-login-form");
  const banner = document.getElementById("login-banner");
  const submitButton = document.getElementById("login-submit");

  // If already signed in, skip straight to the dashboard.
  if (localStorage.getItem(ADMIN_TOKEN_KEY)) {
    window.location.href = "/admin/dashboard.html";
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideBanner(banner);

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    if (!email || !password) {
      showBanner(banner, "Enter both an email address and a password.", "error");
      return;
    }

    setLoading(submitButton, true, "Sign in");

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        showBanner(banner, data.detail || "Could not sign in, please try again.", "error");
        return;
      }

      if (data.role !== "admin") {
        showBanner(
          banner,
          "This account is not registered as an admin. Use the student portal instead.",
          "error"
        );
        return;
      }

      localStorage.setItem(ADMIN_TOKEN_KEY, data.access_token);
      localStorage.setItem(ADMIN_PROFILE_KEY, JSON.stringify(data.profile));
      window.location.href = "dashboard.html";
    } catch (error) {
      showBanner(
        banner,
        "Could not reach the server. Check your connection and try again.",
        "error"
      );
    } finally {
      setLoading(submitButton, false, "Sign in");
    }
  });
});
