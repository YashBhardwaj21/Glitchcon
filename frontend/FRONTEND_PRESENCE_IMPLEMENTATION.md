# Frontend Live Member List Implementation Summary

## Overview

The frontend implements a real-time online presence system using REST API initialization + Socket.IO events. Two implementations exist (being unified):

1. **New approach:** `useCommunityPresence()` custom hook
2. **Current approach:** Direct Socket.IO logic in `ChatArea.jsx`

Both follow the same workflow below.

---

## Architecture & Workflow

### STEP 1: REST API Initialization

**Trigger:** Component mounts (ChatArea or parent that uses the hook)

**Request:**

```
GET /api/communities/:communityId
Authorization: Bearer <jwt_token>
```

**Expected Response:**

```json
{
  "online_members": 3,
  "online_member_list": [
    { "userId": "uuid1", "name": "Alice" },
    { "userId": "uuid2", "name": "Bob" }
  ],
  "members": [
    /* full member list */
  ],
  "total_members": 10
}
```

**Frontend Action:**

- Seed `onlineCount` from `data.online_members`
- Seed `onlineUserIds` (Set) from `data.online_member_list.map(m => m.userId || m.id)`
- Display: "3 / 10 online" in header
- Render member avatars with green dot for online users (those in `onlineUserIds`)

---

### STEP 2: Socket.IO Connection & Join Room

**Trigger:** Immediately after REST API seeding (or if REST fails, still attempt socket connection)

**Socket Connection:**

```javascript
// Connects with JWT in auth header
socket = io(BACKEND_URL, {
  auth: { token: jwt_token },
  transports: ["websocket", "polling"],
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 1000,
});
```

**Client Emits:**

```javascript
socket.emit("join_room", { communityId });
```

**Expected Backend Action:**

1. Authenticate the socket using the JWT from `socket.handshake.auth.token`
2. Extract `userId` and optionally `userName` from the JWT payload
3. Add entry to presence map: `communityPresence[communityId][socketId] = { userId, name }`
4. **Immediately broadcast** `presence_update` to all sockets in the room (including the one that just joined)
5. **Also send** `presence_update` directly to the joining socket to guarantee it receives the current list
6. (Optional) Asynchronously fetch the user's name from the database, and re-broadcast if it differs from the JWT name

**⚡ Race Condition Fix:** The backend broadcasts immediately with JWT name (~0ms) rather than waiting for the DB fetch (~100-200ms). This ensures the joining client receives presence updates without delay. The joining socket also receives the update directly (not just in the room broadcast) for guaranteed delivery across all Socket.IO versions.

---

### STEP 3: Real-time Presence Updates

**Trigger:** Server broadcasts `presence_update`

**Client Listens:**

```javascript
socket.on("presence_update", ({ online_members, members }) => {
  // members = [{ userId: "uuid1", name: "Alice" }, ...]
  setOnlineCount(online_members);
  setOnlineUserIds(new Set(members.map((m) => m.userId || m.id)));
});
```

**Expected Fields in Event:**

```json
{
  "online_members": 3,
  "members": [
    { "userId": "uuid1", "name": "Alice" },
    { "userId": "uuid2", "name": "Bob" },
    { "userId": "uuid3", "name": "Charlie" }
  ]
}
```

**Frontend Updates:**

- `onlineCount` becomes 3
- `onlineUserIds` becomes Set { "uuid1", "uuid2", "uuid3" }
- All avatars auto-update: matching members get green dot, others get grey dot

---

### STEP 4: User Disconnects

**Trigger:** Socket disconnect event on backend (browser tab closed, network lost, etc.)

**Backend Action:**

1. On `socket.disconnect()`, loop through all rooms this socket was in
2. Remove the socket entry from each community's presence map
3. **Broadcast** `presence_update` to all remaining sockets in the room

**Frontend Effect:**

- Same `presence_update` listener fires automatically
- `onlineCount` decreases
- Disconnected user's ID removed from `onlineUserIds`
- Their avatar automatically gets grey dot

---

### STEP 5: Multi-Tab Handling (Deduplication)

**Scenario:** User opens 2+ browser tabs → 2+ socket connections → 2+ entries in the presence map with same `userId`

**Backend Requirement:**
When broadcasting `presence_update`, **deduplicate by `userId`** before sending to clients. Send only **unique user IDs**, not all socket entries.

```javascript
// Example backend deduplication:
const getOnlineMembers = (communityId) => {
  const presence = communityPresence[communityId];
  const uniqueUserIds = new Set();
  const members = [];

  Object.values(presence).forEach(({ userId, name }) => {
    if (!uniqueUserIds.has(userId)) {
      // Only add once per user
      uniqueUserIds.add(userId);
      members.push({ userId, name });
    }
  });

  return {
    online_members: members.length,
    members: members,
  };
};
```

Result: User appears as "1 online" not "2 online", even with 2 tabs open.

---

## Critical Backend Requirements

| Requirement            | Details                                                                                                         |
| ---------------------- | --------------------------------------------------------------------------------------------------------------- |
| **JWT Auth**           | Extract `userId` and optionally `name` from JWT payload on socket connection                                    |
| **join_room Event**    | Listen to `socket.emit('join_room', { communityId })` from client                                               |
| **Presence Map**       | Maintain `communityId → socketId → { userId, name }` mapping                                                    |
| **Broadcast Event**    | Send `presence_update` with `{ online_members, members }` to all sockets in room AND directly to joining socket |
| **Trigger On**         | Send `presence_update` when client joins room AND when any client disconnects                                   |
| **Broadcast Speed**    | Broadcast immediately (~0ms) with JWT name; optionally update if DB fetch completes with different name         |
| **Deduplication**      | Members array should have unique `userId` values (for multi-tab support)                                        |
| **Disconnect Cleanup** | On `socket.disconnect()`, remove socket from all community presence maps and broadcast update                   |

---

## Known Issues & Fixes

### ✅ Race Condition: Emitting join_room Before Socket Connects

**Problem:** The frontend might emit `join_room` before the socket's `connect` event fires, causing the backend to never receive it.

**Solution:** Use `socket.once("connect", ...)` in the frontend hook to defer emission until the socket is truly ready, or check `socket.connected` first.

```javascript
if (socket.connected) {
  socket.emit("join_room", { communityId });
} else {
  socket.once("connect", () => {
    socket.emit("join_room", { communityId });
  });
}
```

**Current Status:** ✅ Fixed in `useCommunityPresence.js`

### ✅ Race Condition: DB Fetch Delaying Broadcast

**Problem:** Backend waits for Supabase name lookup (~100-200ms) before broadcasting `presence_update`, causing the joiner to see delayed or out-of-order updates.

**Solution:** Broadcast immediately with the JWT name, then optionally update if the DB fetch completes with a different name.

**Current Status:** ✅ Fixed on backend (broadcasts with JWT name immediately)

### ✅ Joiner Missing Own Broadcast

**Problem:** `io.to(room).emit(...)` might not reach the socket that just joined due to timing gaps between room join and broadcast.

**Solution:** Send `presence_update` both to the room AND directly to the joining socket to guarantee delivery.

**Current Status:** ✅ Fixed on backend (sends to both room and joining socket)

---

## Frontend State

```javascript
// Managed by useCommunityPresence hook or ChatArea component
const [onlineCount, setOnlineCount] = useState(0); // number
const [onlineUserIds, setOnlineUserIds] = useState(new Set()); // Set<string>

// Usage to check if member is online:
const isOnline = onlineUserIds.has(member.userId); // O(1) lookup
```

---

## Debugging Checklist

Frontend side will log:

```
[useCommunityPresence] Initial state seeded: 3 online
[useCommunityPresence] Emitted join_room for communityId: abc-123
[useCommunityPresence] Received presence_update: { online_members: 3, memberCount: 3 }
```

**If you don't see the `Received presence_update` log**, the backend is likely not broadcasting the event. Check:

- ✅ Is backend receiving the `join_room` event?
- ✅ Is backend calling `io.to(room).emit('presence_update', ...)`?
- ✅ Are members being deduplicated (no duplicate `userId` values)?
- ✅ Is online_members count correct?

---

## Frontend Implementation Files

### `src/hooks/useCommunityPresence.js`

Custom React hook that encapsulates:

- REST API fetch on mount
- Socket.IO connection with JWT
- `join_room` emission
- `presence_update` listener
- Cleanup on unmount

**Usage:**

```javascript
const { onlineCount, onlineUserIds } = useCommunityPresence(communityId, token);
```

### `src/components/ChatArea.jsx`

Currently handles presence logic directly (will be refactored to use hook):

- Fetches community data
- Seeds initial state
- Emits `join_room`
- Listens to `presence_update`
- Passes state up to parent

### `src/socket.js`

Singleton socket factory:

- Creates authenticated Socket.IO connection
- Manages reconnection logic
- Provides `connectSocket(token)` and `disconnectSocket()`

---

## Summary

This is what the frontend is doing to update the live member list:

1. **Bootstrap:** REST API fetch seeds initial online members
2. **Connect:** Socket.IO connects with JWT authentication
3. **Subscribe:** Emit `join_room` and listen to `presence_update` events
4. **Sync:** Update state reactively on every presence broadcast
5. **Cleanup:** Remove listeners on component unmount

The backend needs to:

1. Accept `join_room` events with `communityId`
2. Maintain a presence map per community
3. Broadcast `presence_update` with deduplicated online members
4. Clean up on disconnect and broadcast again to remaining clients

---
