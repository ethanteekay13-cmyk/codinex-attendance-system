// Codinex Attendance System - student login logic.
const API_BASE_URL = "https://codinex-attendance-system.vercel.app/api/v1";

const STUDENT_TOKEN_KEY = "codinex_student_token";
const STUDENT_PROFILE_KEY = "codinex_student_profile";

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

function resolvePostLoginDestination() {
  const params = new URLSearchParams(window.location.search);
  const redirect = params.get("redirect");
  const token = params.get("token");

  if (redirect === "scan" && token) {
    return `scan.html?token=${encodeURIComponent(token)}`;
  }
  return "dashboard.html";
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("student-login-form");
  const banner = document.getElementById("login-banner");
  const submitButton = document.getElementById("login-submit");

  if (localStorage.getItem(STUDENT_TOKEN_KEY)) {
    window.location.href = resolvePostLoginDestination();
    return;
  }

  const params = new URLSearchParams(window.location.search);
  if (params.get("redirect") === "scan") {
    showBanner(
      banner,
      "Sign in to confirm your check-in. You will be returned to the scan screen automatically.",
      "info"
    );
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
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        showBanner(banner, data.detail || "Could not sign in, please try again.", "error");
        return;
      }

      if (data.role !== "student") {
        showBanner(
          banner,
          "This account is not registered as a student. Use the admin sign in instead.",
          "error"
        );
        return;
      }

      localStorage.setItem(STUDENT_TOKEN_KEY, data.access_token);
      localStorage.setItem(STUDENT_PROFILE_KEY, JSON.stringify(data.profile));
      window.location.href = resolvePostLoginDestination();
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
