const supabase = require('../config/db');
const { moderateMessage } = require('../services/moderationService');

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

    // --- join_room ---
    // Payload: { communityId }
    socket.on('join_room', ({ communityId } = {}) => {
      if (!communityId) return;
      socket.join(communityId);
      console.log(`User ${socket.user.id} joined room ${communityId}`);
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
          .select('id, name')
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
    });
  });
};

module.exports = initChatSocket;
