const supabase = require('../config/db');
const { moderateMessage } = require('../services/moderationService');

const EXTERNAL_MODERATION_URL = 'https://commonsmodel-1.onrender.com/query';

function forwardToExternalAPI(payload) {
  fetch(EXTERNAL_MODERATION_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch((err) => console.error('External moderation API error:', err.message));
}

// In-memory presence store: communityId -> Map<socketId, { userId, name }>
// Using socketId as key so one user with multiple tabs is tracked per-socket
const presence = new Map();

function getOnlineMembers(communityId) {
  const room = presence.get(communityId);
  if (!room) return [];
  // Deduplicate by userId (multiple tabs => one entry per user)
  const seen = new Map();
  for (const { userId, name } of room.values()) {
    if (!seen.has(userId)) seen.set(userId, { userId, name });
  }
  return Array.from(seen.values());
}

function broadcastPresence(io, communityId, joiningSocket = null) {
  const members = getOnlineMembers(communityId);
  const payload = {
    communityId,
    online_members: members.length,
    members,
  };
  // Broadcast to everyone in the room
  io.to(communityId).emit('presence_update', payload);
  // Also send directly to the socket that just joined (in case it missed the room broadcast)
  if (joiningSocket) {
    joiningSocket.emit('presence_update', payload);
  }
}

const initChatSocket = (io) => {
  // --- JWT authentication middleware for every socket connection ---
  io.use(async (socket, next) => {
    try {
      const token =
        socket.handshake.auth?.token ||
        socket.handshake.headers?.authorization?.split(' ')[1];

      if (!token) {
        return next(new Error('Authentication error: no token provided'));
      }

      const { data, error } = await supabase.auth.getUser(token);

      if (error || !data.user) {
        return next(new Error('Authentication error: token invalid'));
      }

      socket.user = data.user; // { id, email, user_metadata, ... }
      next();
    } catch (error) {
      next(new Error('Authentication error: token invalid'));
    }
  });

  io.on('connection', (socket) => {
    console.log(`Socket connected: ${socket.id} (user: ${socket.user.id})`);

    // --- leave_room ---
    // Payload: { communityId }
    socket.on('leave_room', ({ communityId } = {}) => {
      if (!communityId) return;
      socket.leave(communityId);

      // Remove from presence map
      const room = presence.get(communityId);
      if (room) {
        room.delete(socket.id);
        if (room.size === 0) presence.delete(communityId);
        else broadcastPresence(io, communityId);
      }

      if (socket.rooms_joined) socket.rooms_joined.delete(communityId);
      console.log(`User ${socket.user.id} left room ${communityId}`);
    });

    // --- join_room ---
    // Payload: { communityId }
    socket.on('join_room', async ({ communityId } = {}) => {
      if (!communityId) return;

      // Skip if this socket already joined this room
      if (socket.rooms_joined && socket.rooms_joined.has(communityId)) return;

      socket.join(communityId);
      console.log(`User ${socket.user.id} joined room ${communityId}`);

      // Track in presence map
      if (!presence.has(communityId)) presence.set(communityId, new Map());

      // Immediately register with whatever name we have from the JWT
      // so broadcastPresence fires without waiting for DB
      const immeditateName = socket.user.user_metadata?.name || null;
      presence.get(communityId).set(socket.id, {
        userId: socket.user.id,
        name: immeditateName,
      });

      // Store which rooms this socket is in so we can clean up on disconnect
      if (!socket.rooms_joined) socket.rooms_joined = new Set();
      socket.rooms_joined.add(communityId);

      // Broadcast immediately — clients get updated count right away
      broadcastPresence(io, communityId, socket);

      // Then fetch the correct display name from DB and re-broadcast if different
      try {
        const { data: profile } = await supabase
          .from('users')
          .select('name')
          .eq('id', socket.user.id)
          .single();

        const dbName = profile?.name || immeditateName;
        if (dbName !== immeditateName) {
          presence.get(communityId)?.set(socket.id, {
            userId: socket.user.id,
            name: dbName,
          });
          broadcastPresence(io, communityId);
        }
      } catch (_) {
        // Non-critical — name already broadcast with JWT value
      }
    });

    // --- send_message ---
    // Payload: { communityId, content }
    socket.on('send_message', async ({ communityId, content } = {}) => {
      if (!communityId || !content?.trim()) return;

      try {
        const trimmedContent = content.trim();

        // 1. Fetch community's generated grammar for moderation context
        const { data: community } = await supabase
          .from('communities')
          .select('grammar, description')
          .eq('id', communityId)
          .single();

        const grammar = community?.grammar || community?.description || 'General community discussion';

        // 2. Run moderation before saving anything
        let moderationResult;
        try {
          moderationResult = await moderateMessage(trimmedContent, grammar);
        } catch (moderationError) {
          console.error('Moderation service error (failing open):', moderationError.message);
          // Fail open — if AI service is down, let the message through
          moderationResult = { approved: true };
        }

        // Fire-and-forget: forward LLM moderation output to external API
        forwardToExternalAPI({
          community_id: communityId,
          message: trimmedContent,
          approved: moderationResult.approved,
          reason: moderationResult.reason || null,
        });

        if (!moderationResult.approved) {
          socket.emit('moderation_alert', {
            blocked: true,
            reason: moderationResult.reason || 'Your message was blocked. Please review the community guidelines.',
          });
          return;
        }

        // 3. Insert message into Supabase
        const { data: message, error } = await supabase
          .from('messages')
          .insert({
            community_id: communityId,
            sender_id: socket.user.id,
            content: trimmedContent,
          })
          .select('id, community_id, content, created_at, sender_id')
          .single();

        if (error) {
          console.error('send_message DB error:', error.message);
          socket.emit('error', { message: 'Failed to send message' });
          return;
        }

        // 4. Fetch sender details and broadcast
        const { data: sender } = await supabase
          .from('users')
          .select('id, name, avatar_url')
          .eq('id', socket.user.id)
          .single();

        io.to(communityId).emit('receive_message', { ...message, sender: sender || null });
      } catch (error) {
        console.error('send_message error:', error.message);
        socket.emit('error', { message: 'Failed to send message' });
      }
    });

    socket.on('disconnect', () => {
      console.log(`Socket disconnected: ${socket.id}`);

      // Remove from all rooms this socket had joined and broadcast updated presence
      if (socket.rooms_joined) {
        for (const communityId of socket.rooms_joined) {
          const room = presence.get(communityId);
          if (room) {
            room.delete(socket.id);
            if (room.size === 0) presence.delete(communityId);
            else broadcastPresence(io, communityId);
          }
        }
      }
    });
  });
};

module.exports = initChatSocket;
module.exports.getOnlineMembers = getOnlineMembers;
