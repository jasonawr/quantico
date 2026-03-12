const statusEl = document.getElementById("accountStatus");
const infoEl = document.getElementById("accountInfo");

function getToken() {
  return localStorage.getItem("jc_session_token") || "";
}

function setToken(token) {
  if (token) localStorage.setItem("jc_session_token", token);
  else localStorage.removeItem("jc_session_token");
}

async function api(path, method = "GET", body = null) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== null) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: body !== null ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function showUser(user) {
  infoEl.innerHTML = `<div><strong>${user.display_name}</strong> (${user.email})</div><div>User ID: ${user.id}</div><div>Created: ${user.created_at}</div>`;
}

async function refreshMe() {
  try {
    const data = await api("/api/auth/me");
    showUser(data.user);
    statusEl.textContent = "Connected";
  } catch {
    infoEl.textContent = "No active session.";
    statusEl.textContent = "Disconnected";
  }
}

async function register() {
  const payload = {
    email: document.getElementById("regEmail").value.trim(),
    display_name: document.getElementById("regName").value.trim(),
    password: document.getElementById("regPassword").value,
  };
  const data = await api("/api/auth/register", "POST", payload);
  setToken(data.token);
  await refreshMe();
}

async function login() {
  const payload = {
    email: document.getElementById("loginEmail").value.trim(),
    password: document.getElementById("loginPassword").value,
  };
  const data = await api("/api/auth/login", "POST", payload);
  setToken(data.token);
  await refreshMe();
}

async function logout() {
  try {
    await api("/api/auth/logout", "POST", {});
  } catch {}
  setToken("");
  await refreshMe();
}

document.getElementById("registerBtn").addEventListener("click", () => register().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("loginBtn").addEventListener("click", () => login().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("logoutBtn").addEventListener("click", () => logout().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));

(async () => {
  await refreshMe();
})();
