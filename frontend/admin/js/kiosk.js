// Codinex Attendance System - kiosk display logic.
const API_BASE_URL = "https://codinex-attendance-system.vercel.app/api/v1";

// The domain students' phones are sent to when they scan the QR code.
// Update this to match your real deployed frontend domain.
const STUDENT_SCAN_BASE_URL = "https://codinex-attendance-system-nshx.vercel.app/student/scan.html";

const ADMIN_TOKEN_KEY = "codinex_admin_token";

let qrCodeInstance = null;
let lastRenderedToken = null;

function renderQrCode(scanUrl) {
  const container = document.getElementById("qr-code-container");
  if (qrCodeInstance) {
    qrCodeInstance.clear();
    qrCodeInstance.makeCode(scanUrl);
    return;
  }
  qrCodeInstance = new QRCode(container, {
    text: scanUrl,
    width: 280,
    height: 280,
    colorDark: "#0f172a",
    colorLight: "#f5f7fb",
    correctLevel: QRCode.CorrectLevel.M,
  });
}

function updateCountdownRing(secondsRemaining, windowSeconds) {
  const ring = document.getElementById("countdown-ring");
  const label = document.getElementById("countdown-value");
  const percent = Math.round((secondsRemaining / windowSeconds) * 100);
  ring.style.setProperty("--ring-percent", String(percent));
  label.textContent = String(secondsRemaining);
}

async function refreshQrToken() {
  const statusEl = document.getElementById("connection-status");
  try {
    const response = await fetch(`${API_BASE_URL}/attendance/qr-token`);
    if (!response.ok) {
      throw new Error("Non-200 response");
    }
    const data = await response.json();

    updateCountdownRing(data.seconds_remaining, data.window_seconds);

    if (data.token !== lastRenderedToken) {
      lastRenderedToken = data.token;
      const scanUrl = `${STUDENT_SCAN_BASE_URL}?token=${encodeURIComponent(data.token)}`;
      renderQrCode(scanUrl);
      document.getElementById("token-text").textContent = data.token;
    }

    statusEl.textContent = "Live";
    statusEl.classList.remove("is-offline");
  } catch (error) {
    statusEl.textContent = "Reconnecting...";
    statusEl.classList.add("is-offline");
  }
}

async function refreshLiveCount() {
  const countEl = document.getElementById("live-count-value");
  const noteEl = document.getElementById("live-count-note");
  const adminToken = localStorage.getItem(ADMIN_TOKEN_KEY);

  if (!adminToken) {
    countEl.textContent = "--";
    noteEl.textContent = "Sign in as an admin and open this kiosk from the dashboard to show a live count.";
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/admin/dashboard-summary`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    if (!response.ok) {
      throw new Error("Could not load dashboard summary");
    }
    const data = await response.json();
    countEl.textContent = String(data.present + data.late);
    noteEl.textContent = `of ${data.total_students} students checked in today`;
  } catch (error) {
    countEl.textContent = "--";
    noteEl.textContent = "Live count unavailable.";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  refreshQrToken();
  refreshLiveCount();
  setInterval(refreshQrToken, 1000);
  setInterval(refreshLiveCount, 5000);
});
