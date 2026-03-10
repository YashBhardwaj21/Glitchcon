# Online Presence & Live User Count — Complete Workflow

## Architecture Overview

The online presence system uses **two channels** working together:

| Channel | Purpose | When to use |
|---------|---------|-------------|
| **Socket.io events** | Real-time push updates (instant) | User joins/leaves a community chat |
| **REST API responses** | Snapshot data (on demand) | Loading community list, community details page |

```
┌──────────────┐          ┌──────────────────────┐
│   Frontend   │◄────────►│   Socket.io Server   │
│              │  events   │                      │
│              │          │  In-memory presence   │
│              │          │  Map<communityId,     │
│              │          │    Map<socketId,      │
│              │          │      {userId, name}>> │
│              │          └──────────┬───────────┘
│              │                     │ imported
│              │          ┌──────────▼───────────┐
│              │◄────────►│   REST Controllers   │
│              │  HTTP     │  (communityController)│
└──────────────┘          └──────────────────────┘
```

---

## Data Structure (Server-Side)

```
File: Sockets/chatSocket.js

const presence = new Map();
// Structure:
// {
//   "community-uuid-1": Map {
//     "socketId-A" => { userId: "user-uuid-1", name: "Alice" },
//     "socketId-B" => { userId: "user-uuid-2", name: "Bob" },
//     "socketId-C" => { userId: "user-uuid-1", name: "Alice" }  // same user, 2nd tab
//   },
//   "community-uuid-2": Map { ... }
// }
```

**Key design decisions:**
- Keyed by `socketId` so each browser tab is tracked independently
- `getOnlineMembers()` deduplicates by `userId` — a user with 3 tabs open counts as 1 online member
- The map is **in-memory only** — it resets on server restart (clients auto-reconnect and re-populate it)

---

## Socket.io Events — Complete Reference

### Events the Frontend EMITS (client → server)

#### 1. `join_room`

Emitted when the user opens a community chat screen.

```js
socket.emit('join_room', { communityId: 'uuid-of-community' });
```

**What the server does:**
1. Guards against duplicate joins (skips if this socket already joined this room)
2. Adds the socket to the Socket.io room via `socket.join(communityId)`
3. Registers the user in the presence map with their JWT display name
4. Broadcasts `presence_update` to ALL sockets in the room + directly to the joining socket
5. Asynchronously fetches the user's DB display name; if different from JWT, updates presence and re-broadcasts

#### 2. `leave_room`

Emitted when the user navigates AWAY from a community chat (e.g., back to community list, switching to another community).

```js
socket.emit('leave_room', { communityId: 'uuid-of-community' });
```

**What the server does:**
1. Removes the socket from the Socket.io room
2. Removes the socket from the presence map
3. Broadcasts updated `presence_update` to remaining sockets in the room
4. Removes the community from `socket.rooms_joined`

**Important:** Always emit `leave_room` before emitting `join_room` for a different community. Otherwise the user appears online in both communities simultaneously.

#### 3. `send_message`

```js
socket.emit('send_message', { communityId: 'uuid', content: 'Hello!' });
```

(Not presence-related, but included for completeness. See messaging docs.)

---

### Events the Frontend LISTENS TO (server → client)

#### 1. `presence_update` ← **This is the core presence event**

Fired whenever someone joins or leaves a community room.

```js
socket.on('presence_update', (data) => {
  // data = {
  //   communityId: "uuid-of-community",
  //   online_members: 3,              // deduplicated count
  //   members: [
  //     { userId: "uuid-1", name: "Alice" },
  //     { userId: "uuid-2", name: "Bob" },
  //     { userId: "uuid-3", name: "Charlie" }
  //   ]
  // }
});
```

**When is this emitted?**

| Trigger | Who receives it |
|---------|----------------|
| User A joins room X | All sockets in room X + User A directly |
| User A disconnects from room X | All remaining sockets in room X |
| User A emits `leave_room` for room X | All remaining sockets in room X |
| User A's DB name differs from JWT name (rare) | All sockets in room X (re-broadcast) |

**Frontend should:**
- Update the online member count badge
- Update the online members list (sidebar, popover, etc.)
- Replace the entire list with `data.members` (don't try to diff — the server sends the full deduplicated list each time)

#### 2. `receive_message`

```js
socket.on('receive_message', (message) => {
  // message = {
  //   id, content, type, audio_url, created_at, sender_id,
  //   sender: { id, name, avatar_url }
  // }
});
```

#### 3. `moderation_alert`

```js
socket.on('moderation_alert', (data) => {
  // data = { blocked: true, reason: "..." }
});
```

#### 4. `message_deleted`

```js
socket.on('message_deleted', (data) => {
  // data = { messageId: "uuid" }
});
```

---

### Automatic: `disconnect`

When the socket connection drops (tab close, network loss, page refresh):
- Server removes the socket from ALL communities it had joined
- Server broadcasts updated `presence_update` to each affected community room
- No frontend action needed — Socket.io handles disconnect automatically

---

## REST API Endpoints with Presence Data

### `GET /api/communities`

Returns ALL communities with live online counts.

```json
[
  {
    "id": "uuid",
    "name": "Physics Study Group",
    "description": "...",
    "owner_id": "uuid",
    "avatar_url": "https://...",
    "created_at": "2026-01-15T...",
    "total_members": 42,
    "online_members": 5,
    "members": [
      { "id": "uuid", "name": "Alice", "email": "...", "avatar_url": "...", "role": "admin" },
      ...
    ]
  }
]
```

### `GET /api/communities/me`

Returns communities the authenticated user has joined, with live online counts.

```json
[
  {
    "id": "uuid",
    "name": "Physics Study Group",
    "description": "...",
    "owner_id": "uuid",
    "avatar_url": "https://...",
    "created_at": "2026-01-15T...",
    "role": "admin",
    "total_members": 42,
    "online_members": 5
  }
]
```

### `GET /api/communities/:communityId`

Returns a single community's details with full online member list.

```json
{
  "id": "uuid",
  "name": "Physics Study Group",
  "description": "...",
  "owner_id": "uuid",
  "avatar_url": "https://...",
  "created_at": "2026-01-15T...",
  "total_members": 42,
  "online_members": 5,
  "online_member_list": [
    { "userId": "uuid-1", "name": "Alice" },
    { "userId": "uuid-2", "name": "Bob" }
  ],
  "members": [
    { "id": "uuid", "name": "Alice", "email": "...", "avatar_url": "...", "role": "admin" },
    ...
  ]
}
```

---

## Complete Frontend Integration — Step by Step

### Step 1: Connect Socket with JWT Auth

```js
import { io } from 'socket.io-client';

const socket = io('https://your-backend.com', {
  auth: { token: userJwtToken },
  autoConnect: true,
  reconnection: true,
});
```

### Step 2: Register the `presence_update` listener ONCE (globally)

```js
// Do this ONCE when the socket connects,
// NOT inside component mount/unmount cycles
socket.on('presence_update', (data) => {
  // data.communityId — which community this update is for
  // data.online_members — count (number)
  // data.members — full list of { userId, name }

  // Update your state/store with the new data
  updateOnlineMembers(data.communityId, data.online_members, data.members);
});
```

### Step 3: Join a Community Room

When the user navigates to a community chat screen:

```js
function enterCommunity(communityId) {
  // Leave the previous room first (if any)
  if (currentCommunityId && currentCommunityId !== communityId) {
    socket.emit('leave_room', { communityId: currentCommunityId });
  }

  // Join the new room
  socket.emit('join_room', { communityId });
  currentCommunityId = communityId;
}
```

### Step 4: Leave a Community Room

When the user navigates away:

```js
function leaveCommunity() {
  if (currentCommunityId) {
    socket.emit('leave_room', { communityId: currentCommunityId });
    currentCommunityId = null;
  }
}
```

### Step 5: Fetch Initial Data via REST (Optional)

On page load, before Socket establishes, fetch snapshot data:

```js
// For community list page
const res = await fetch('/api/communities', { headers: { Authorization: `Bearer ${token}` } });
const communities = await res.json();
// Each community has: total_members, online_members

// For community detail page
const res = await fetch(`/api/communities/${communityId}`, { headers: { Authorization: `Bearer ${token}` } });
const details = await res.json();
// Has: total_members, online_members, online_member_list, members
```

---

## Lifecycle Sequence Diagram

### User Opens Community Chat
```
Frontend                          Backend (Socket.io)
   │                                     │
   │──── connect (auth: {token}) ────────►│
   │                                     │ Validate JWT
   │◄──── connection established ────────│
   │                                     │
   │──── emit('join_room', {communityId})►│
   │                                     │ socket.join(communityId)
   │                                     │ presence.set(communityId, socketId → user)
   │                                     │
   │◄── emit('presence_update') ─────────│  (to the joiner directly)
   │◄── emit('presence_update') ─────────│  (to all room members via io.to)
   │                                     │
   │  Update UI: show online count       │
   │  Update UI: show member list        │
```

### User Switches to Another Community
```
Frontend                          Backend (Socket.io)
   │                                     │
   │── emit('leave_room', {communityA}) ─►│
   │                                     │ socket.leave(communityA)
   │                                     │ presence.delete(socketId from A)
   │                                     │
   │◄── presence_update for A ───────────│  (to remaining members in A)
   │                                     │
   │── emit('join_room', {communityB}) ──►│
   │                                     │ socket.join(communityB)
   │                                     │ presence.set(communityB, socketId → user)
   │                                     │
   │◄── presence_update for B ───────────│  (to the joiner + all in B)
```

### User Closes Tab / Disconnects
```
Frontend                          Backend (Socket.io)
   │                                     │
   │──── TCP disconnect ────────────────►│
   │                                     │ for each room in socket.rooms_joined:
   │                                     │   presence.delete(socketId)
   │                                     │   broadcastPresence(remaining members)
   │                                     │
   │  (User gone)                        │ Other users in those rooms receive
   │                                     │ updated presence_update events
```

### Multi-Tab Scenario
```
Tab 1 (socket-A) joins Community X  →  presence = { X: { socket-A: user1 } }
Tab 2 (socket-B) joins Community X  →  presence = { X: { socket-A: user1, socket-B: user1 } }

getOnlineMembers(X) returns: [{ userId: user1, name: "Alice" }]  ← deduplicated!
online_members count = 1  (not 2)

Tab 1 closes  →  presence = { X: { socket-B: user1 } }
getOnlineMembers(X) still returns: [{ userId: user1, name: "Alice" }]
online_members count = 1  ← user is still online via Tab 2

Tab 2 closes  →  presence = {}  (community X removed entirely)
presence_update → online_members = 0, members = []
```

---

## Anomalies Found & Fixed

### 1. Duplicate `join_room` calls not guarded
**Problem:** The frontend could emit `join_room` for the same community multiple times (e.g., React re-renders). Each call triggered a redundant `broadcastPresence` to all room members.

**Fix:** Added an early-return guard in `join_room`:
```js
if (socket.rooms_joined && socket.rooms_joined.has(communityId)) return;
```

### 2. No `leave_room` event
**Problem:** When a user navigated from Community A to Community B, they emitted `join_room` for B but never left A. The user appeared "online" in both communities until the socket disconnected entirely.

**Fix:** Added a `leave_room` socket event handler. The frontend should emit `leave_room` before `join_room` when switching communities.

### 3. `getUserCommunities` (GET /api/communities/me) missing online counts
**Problem:** `getAllCommunities` returned `total_members` and `online_members`, but `getUserCommunities` returned neither. The "My Communities" page couldn't show online counts without extra API calls.

**Fix:** Added `total_members` and `online_members` fields to the `getUserCommunities` response.

---

## Summary of All Presence-Related Code Locations

| File | What it does |
|------|-------------|
| `Sockets/chatSocket.js` | Core presence Map, `getOnlineMembers()`, `broadcastPresence()`, `join_room`, `leave_room`, `disconnect` handlers |
| `controllers/communityController.js` | `getAllCommunities`, `getUserCommunities`, `getCommunityDetails` — all call `getOnlineMembers()` for REST snapshot data |
| `server.js` | Creates Socket.io server, calls `initChatSocket(io)`, stores `io` via `app.set('io', io)` |

## Socket Events Quick Reference

| Event | Direction | Payload | Purpose |
|-------|-----------|---------|---------|
| `join_room` | Client → Server | `{ communityId }` | Enter a community room |
| `leave_room` | Client → Server | `{ communityId }` | Leave a community room |
| `presence_update` | Server → Client | `{ communityId, online_members, members }` | Live count + member list update |
| `send_message` | Client → Server | `{ communityId, content }` | Send a chat message |
| `receive_message` | Server → Client | `{ id, content, type, audio_url, created_at, sender_id, sender }` | New message broadcast |
| `moderation_alert` | Server → Client | `{ blocked, reason }` | Message was blocked by AI |
| `message_deleted` | Server → Client | `{ messageId }` | A message was deleted |
