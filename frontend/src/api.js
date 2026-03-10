const BASE = `${import.meta.env.VITE_BACKEND_URL}/api`;

function headers(token, json = false) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

async function request(url, opts) {
  const res = await fetch(url, opts);
  const body = res.headers.get("content-type")?.includes("json")
    ? await res.json()
    : null;
  if (!res.ok) throw { status: res.status, ...(body || {}) };
  return body;
}

/* ── Auth ── */
export const register = (name, email, password, avatar) => {
  const fd = new FormData();
  fd.append("name", name);
  fd.append("email", email);
  fd.append("password", password);
  if (avatar) fd.append("avatar", avatar);
  return request(`${BASE}/auth/register`, {
    method: "POST",
    headers: headers(null, false),
    body: fd,
  });
};

export const login = (email, password) =>
  request(`${BASE}/auth/login`, {
    method: "POST",
    headers: headers(null, true),
    body: JSON.stringify({ email, password }),
  });

export const logout = (token) =>
  request(`${BASE}/auth/logout`, {
    method: "POST",
    headers: headers(token),
  });

/* ── Communities ── */
export const getCommunities = (token) =>
  request(`${BASE}/communities`, { headers: headers(token) });

export const getMyCommunities = (token) =>
  request(`${BASE}/communities/me`, { headers: headers(token) });

export const createCommunity = (
  token,
  name,
  description,
  restricted_words,
  avatar,
) => {
  const fd = new FormData();
  fd.append("name", name);
  if (description) fd.append("description", description);
  const words = Array.isArray(restricted_words) ? restricted_words : [];
  if (words.length) fd.append("restricted_words", JSON.stringify(words));
  if (avatar) fd.append("avatar", avatar);
  return request(`${BASE}/communities`, {
    method: "POST",
    headers: headers(token, false),
    body: fd,
  });
};

export const updateCommunity = (token, communityId, updates) =>
  request(`${BASE}/communities/${communityId}`, {
    method: "PATCH",
    headers: headers(token, true),
    body: JSON.stringify({
      ...updates,
      restricted_words: Array.isArray(updates.restricted_words)
        ? updates.restricted_words
        : [],
    }),
  });

export const joinCommunity = (token, communityId) =>
  request(`${BASE}/communities/${communityId}/join`, {
    method: "POST",
    headers: headers(token),
  });

/* ── Messages ── */
export const getMessages = (token, communityId) =>
  request(`${BASE}/communities/${communityId}/messages`, {
    headers: headers(token),
  });

export const getCommunity = (token, communityId) =>
  request(`${BASE}/communities/${communityId}`, {
    headers: headers(token),
  });

export const sendMessage = (token, communityId, content) =>
  request(`${BASE}/communities/${communityId}/messages`, {
    method: "POST",
    headers: headers(token, true),
    body: JSON.stringify({ content }),
  });

export const sendAudioMessage = (
  token,
  communityId,
  audioBlob,
  transcription,
) => {
  const fd = new FormData();
  fd.append("type", "audio");
  fd.append("transcription", transcription);
  fd.append("audio", audioBlob, "audio.webm");

  // Debug logging
  console.log("[API] Sending audio message with:");
  console.log("  - type: audio");
  console.log("  - transcription:", transcription);
  console.log("  - audio blob:", audioBlob);
  console.log("  - audio file name: audio.webm");
  console.log("[API] Form data entries:", {
    type: fd.get("type"),
    transcription: fd.get("transcription"),
    audioFile: fd.get("audio"),
  });

  return request(`${BASE}/communities/${communityId}/messages`, {
    method: "POST",
    headers: headers(token, false),
    body: fd,
  });
};

/* ── Admin ── */
export const addAdmin = (token, communityId, userId) =>
  request(`${BASE}/communities/${communityId}/admins`, {
    method: "POST",
    headers: headers(token, true),
    body: JSON.stringify({ userId }),
  });

export const removeAdmin = (token, communityId, userId) =>
  request(`${BASE}/communities/${communityId}/admins/${userId}`, {
    method: "DELETE",
    headers: headers(token),
  });

export const deleteCommunity = (token, communityId) =>
  request(`${BASE}/communities/${communityId}`, {
    method: "DELETE",
    headers: headers(token),
  });

export const leaveCommunity = (token, communityId) =>
  request(`${BASE}/communities/${communityId}/leave`, {
    method: "DELETE",
    headers: headers(token),
  });

export const deleteMessage = (token, communityId, messageId) =>
  request(`${BASE}/communities/${communityId}/messages/${messageId}`, {
    method: "DELETE",
    headers: headers(token),
  });

export const removeMember = (token, communityId, userId) =>
  request(`${BASE}/communities/${communityId}/members/${userId}`, {
    method: "DELETE",
    headers: headers(token),
  });
