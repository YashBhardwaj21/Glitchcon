const supabase = require('../config/db');
const { generateCommunityGrammar } = require('../services/promptGenerator');
const path = require('path');
const { uploadToSupabase, BUCKET_COMMUNITIES, BUCKET_AUDIO } = require('./uploadController');

// POST /api/communities
const createCommunity = async (req, res) => {
  try {
    const { name, description, restricted_words } = req.body;

    if (!name) {
      return res.status(400).json({ message: 'Community name is required' });
    }

    // Ensure restricted_words is always stored as an array
    const words = Array.isArray(restricted_words) ? restricted_words : [];

    // Generate AI moderation grammar for this community
    let grammar = null;
    try {
      grammar = await generateCommunityGrammar(description || '', words);
    } catch (grammarError) {
      console.error('Grammar generation failed (proceeding without):', grammarError.message);
    }

    const { data: community, error } = await supabase
      .from('communities')
      .insert({ name, description, owner_id: req.user.id, restricted_words: words, grammar })
      .select()
      .single();

    if (error) {
      console.error('createCommunity DB error:', error.message);
      return res.status(500).json({ message: 'Failed to create community' });
    }

    // Upload community avatar if provided
    let avatar_url = null;
    if (req.file) {
      try {
        const ext = path.extname(req.file.originalname) || '.jpg';
        avatar_url = await uploadToSupabase(BUCKET_COMMUNITIES, `${community.id}${ext}`, req.file.buffer, req.file.mimetype);
        await supabase.from('communities').update({ avatar_url }).eq('id', community.id);
        community.avatar_url = avatar_url;
      } catch (uploadErr) {
        console.error('Community avatar upload failed (proceeding without):', uploadErr.message);
      }
    }

    // Seed the creator as a member with role 'admin'
    await supabase
      .from('community_roles')
      .insert({ community_id: community.id, user_id: req.user.id, role: 'admin' });

    return res.status(201).json(community);
  } catch (error) {
    console.error('createCommunity error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// POST /api/communities/:communityId/admins
// req.community is attached by isCommunityOwnerOrAdmin middleware
const addAdmin = async (req, res) => {
  try {
    const { userId } = req.body;

    if (!userId) {
      return res.status(400).json({ message: 'userId is required' });
    }

    // Upsert: if already a member, promote to admin; otherwise insert fresh
    const { error } = await supabase
      .from('community_roles')
      .upsert(
        { community_id: req.params.communityId, user_id: userId, role: 'admin' },
        { onConflict: 'community_id,user_id' }
      );

    if (error) {
      console.error('addAdmin DB error:', error.message);
      return res.status(500).json({ message: 'Failed to add admin' });
    }

    return res.status(200).json({ message: 'User promoted to admin' });
  } catch (error) {
    console.error('addAdmin error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// GET /api/communities
const getAllCommunities = async (req, res) => {
  try {
    // 1. Fetch all communities
    const { data: communities, error } = await supabase
      .from('communities')
      .select('id, name, description, owner_id, avatar_url, created_at')
      .order('created_at', { ascending: false });

    if (error) {
      console.error('getAllCommunities DB error:', error.message);
      return res.status(500).json({ message: 'Failed to fetch communities' });
    }

    if (!communities || communities.length === 0) {
      return res.status(200).json([]);
    }

    const communityIds = communities.map((c) => c.id);

    // 2. Fetch all roles for those communities in one query
    const { data: allRoles, error: rolesError } = await supabase
      .from('community_roles')
      .select('community_id, user_id, role')
      .in('community_id', communityIds);

    if (rolesError) {
      console.error('getAllCommunities roles error:', rolesError.message);
      return res.status(500).json({ message: 'Failed to fetch member data' });
    }

    // 3. Batch-fetch all relevant users
    const userIds = [...new Set((allRoles || []).map((r) => r.user_id))];
    let usersMap = {};

    if (userIds.length > 0) {
      const { data: users, error: usersError } = await supabase
        .from('users')
        .select('id, name, email, avatar_url')
        .in('id', userIds);

      if (!usersError) {
        usersMap = Object.fromEntries((users || []).map((u) => [u.id, u]));
      }
    }

    // 4. Get online users per community via Socket.io rooms
    const io = req.app.get('io');
    const onlinePerCommunity = {};
    for (const communityId of communityIds) {
      const room = io?.sockets?.adapter?.rooms?.get(communityId);
      const onlineUserIds = new Set();
      if (room) {
        for (const socketId of room) {
          const socket = io.sockets.sockets.get(socketId);
          if (socket?.user?.id) onlineUserIds.add(socket.user.id);
        }
      }
      onlinePerCommunity[communityId] = onlineUserIds.size;
    }

    // 5. Build enriched community list
    const result = communities.map((community) => {
      const members = (allRoles || [])
        .filter((r) => r.community_id === community.id)
        .map((r) => {
          const user = usersMap[r.user_id];
          return {
            id: r.user_id,
            name: user?.name || null,
            email: user?.email || null,
            avatar_url: user?.avatar_url || null,
            role: r.role,
          };
        });

      return {
        ...community,
        total_members: members.length,
        online_members: onlinePerCommunity[community.id] || 0,
        members,
      };
    });

    return res.status(200).json(result);
  } catch (error) {
    console.error('getAllCommunities error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// GET /api/communities/me
const getUserCommunities = async (req, res) => {
  try {
    const { data: roles, error } = await supabase
      .from('community_roles')
      .select('community_id, role')
      .eq('user_id', req.user.id);

    if (error) {
      console.error('getUserCommunities roles error:', error.message);
      return res.status(500).json({ message: 'Failed to fetch your communities' });
    }

    if (!roles || roles.length === 0) {
      return res.status(200).json([]);
    }

    const communityIds = roles.map((r) => r.community_id);

    const { data: communities, error: commError } = await supabase
      .from('communities')
      .select('id, name, description, owner_id, avatar_url, created_at')
      .in('id', communityIds)
      .order('created_at', { ascending: false });

    if (commError) {
      console.error('getUserCommunities communities error:', commError.message);
      return res.status(500).json({ message: 'Failed to fetch your communities' });
    }

    // Attach the user's role to each community
    const roleMap = Object.fromEntries(roles.map((r) => [r.community_id, r.role]));
    const result = communities.map((c) => ({ ...c, role: roleMap[c.id] }));

    return res.status(200).json(result);
  } catch (error) {
    console.error('getUserCommunities error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// POST /api/communities/:communityId/join
const joinCommunity = async (req, res) => {
  try {
    const { communityId } = req.params;

    // Verify community exists
    const { data: community, error: communityError } = await supabase
      .from('communities')
      .select('id')
      .eq('id', communityId)
      .single();

    if (communityError || !community) {
      return res.status(404).json({ message: 'Community not found' });
    }

    // Insert member role; conflict means already a member
    const { error } = await supabase
      .from('community_roles')
      .insert({ community_id: communityId, user_id: req.user.id, role: 'member' });

    if (error) {
      if (error.code === '23505') {
        // Postgres unique violation
        return res.status(409).json({ message: 'Already a member of this community' });
      }
      console.error('joinCommunity DB error:', error.message);
      return res.status(500).json({ message: 'Failed to join community' });
    }

    return res.status(200).json({ message: 'Joined community successfully' });
  } catch (error) {
    console.error('joinCommunity error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// GET /api/communities/:communityId/messages
const getCommunityMessages = async (req, res) => {
  try {
    const { communityId } = req.params;

    // Verify community exists
    const { data: community, error: communityError } = await supabase
      .from('communities')
      .select('id')
      .eq('id', communityId)
      .single();

    if (communityError || !community) {
      return res.status(404).json({ message: 'Community not found' });
    }

    // Fetch last 50 messages then look up sender names explicitly
    const { data: messages, error } = await supabase
      .from('messages')
      .select('id, community_id, content, type, audio_url, created_at, sender_id')
      .eq('community_id', communityId)
      .order('created_at', { ascending: false })
      .limit(50);

    if (error) {
      console.error('getCommunityMessages DB error:', error.message);
      return res.status(500).json({ message: 'Failed to fetch messages' });
    }

    // Batch-fetch sender profiles
    const senderIds = [...new Set(messages.map((m) => m.sender_id))];
    const { data: users } = senderIds.length
      ? await supabase.from('users').select('id, name').in('id', senderIds)
      : { data: [] };
    const usersMap = Object.fromEntries((users || []).map((u) => [u.id, u]));

    const result = messages
      .map((m) => ({ ...m, sender: usersMap[m.sender_id] || null }))
      .reverse();

    return res.status(200).json(result);
  } catch (error) {
    console.error('getCommunityMessages error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// POST /api/communities/:communityId/messages
const sendMessage = async (req, res) => {
  try {
    const { communityId } = req.params;
    const type = req.body.type === 'audio' ? 'audio' : 'text';
    const content = type === 'audio' ? req.body.transcription?.trim() : req.body.content?.trim();

    if (!content) {
      return res.status(400).json({ message: 'Message content cannot be empty' });
    }

    // Verify the sender is a member or admin/owner of the community
    const { data: roleRow } = await supabase
      .from('community_roles')
      .select('role')
      .eq('community_id', communityId)
      .eq('user_id', req.user.id)
      .maybeSingle();

    if (!roleRow) {
      return res.status(403).json({ message: 'You are not a member of this community' });
    }

    // For audio messages: upload the audio file first
    let audio_url = null;
    if (type === 'audio') {
      if (!req.file) {
        return res.status(400).json({ message: 'Audio file is required for audio messages' });
      }
      try {
        const path = require('path');
        const ext = path.extname(req.file.originalname) || '.webm';
        audio_url = await uploadToSupabase(
          BUCKET_AUDIO,
          `${communityId}/${req.user.id}_${Date.now()}${ext}`,
          req.file.buffer,
          req.file.mimetype
        );
      } catch (uploadErr) {
        console.error('Audio upload error:', uploadErr.message);
        return res.status(500).json({ message: 'Failed to upload audio' });
      }
    }

    // Insert the message
    const { data: message, error } = await supabase
      .from('messages')
      .insert({ community_id: communityId, sender_id: req.user.id, content, type, audio_url })
      .select('id, content, type, audio_url, created_at, sender_id')
      .single();

    if (error) {
      console.error('sendMessage DB error:', error.message);
      return res.status(500).json({ message: 'Failed to send message' });
    }

    const { data: sender } = await supabase
      .from('users')
      .select('id, name')
      .eq('id', req.user.id)
      .single();

    const messageWithSender = { ...message, sender: sender || null };

    // Broadcast to all sockets in the community room in real-time
    const io = req.app.get('io');
    io.to(communityId).emit('receive_message', messageWithSender);

    return res.status(201).json(messageWithSender);
  } catch (error) {
    console.error('sendMessage error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// DELETE /api/communities/:communityId — owner only
const deleteCommunity = async (req, res) => {
  try {
    // Cascades delete community_roles and messages via FK ON DELETE CASCADE
    const { error } = await supabase
      .from('communities')
      .delete()
      .eq('id', req.params.communityId);

    if (error) {
      console.error('deleteCommunity DB error:', error.message);
      return res.status(500).json({ message: 'Failed to delete community' });
    }

    return res.status(200).json({ message: 'Community deleted successfully' });
  } catch (error) {
    console.error('deleteCommunity error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// DELETE /api/communities/:communityId/messages/:messageId
// Own message: any member; any message: owner or admin
const deleteMessage = async (req, res) => {
  try {
    const { communityId, messageId } = req.params;
    const userId = req.user.id;

    // Fetch the message to check ownership
    const { data: message, error: fetchError } = await supabase
      .from('messages')
      .select('id, sender_id')
      .eq('id', messageId)
      .eq('community_id', communityId)
      .single();

    if (fetchError || !message) {
      return res.status(404).json({ message: 'Message not found' });
    }

    // Allow if sender, otherwise require owner/admin role
    if (message.sender_id !== userId) {
      const { data: community } = await supabase
        .from('communities')
        .select('owner_id')
        .eq('id', communityId)
        .single();

      const isOwner = community?.owner_id === userId;

      if (!isOwner) {
        const { data: roleRow } = await supabase
          .from('community_roles')
          .select('role')
          .eq('community_id', communityId)
          .eq('user_id', userId)
          .eq('role', 'admin')
          .maybeSingle();

        if (!roleRow) {
          return res.status(403).json({ message: 'Access denied: not your message' });
        }
      }
    }

    const { error } = await supabase
      .from('messages')
      .delete()
      .eq('id', messageId);

    if (error) {
      console.error('deleteMessage DB error:', error.message);
      return res.status(500).json({ message: 'Failed to delete message' });
    }

    // Notify room members so clients can remove the message from their UI
    const io = req.app.get('io');
    io.to(communityId).emit('message_deleted', { messageId });

    return res.status(200).json({ message: 'Message deleted successfully' });
  } catch (error) {
    console.error('deleteMessage error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// DELETE /api/communities/:communityId/admins/:userId — owner or admin only
const removeAdmin = async (req, res) => {
  try {
    const { communityId, userId } = req.params;

    // Cannot demote the owner
    const community = req.community;
    if (community.owner_id === userId) {
      return res.status(400).json({ message: 'Cannot remove admin role from the owner' });
    }

    // Downgrade role to member instead of removing the row entirely
    const { error } = await supabase
      .from('community_roles')
      .update({ role: 'member' })
      .eq('community_id', communityId)
      .eq('user_id', userId)
      .eq('role', 'admin');

    if (error) {
      console.error('removeAdmin DB error:', error.message);
      return res.status(500).json({ message: 'Failed to remove admin' });
    }

    return res.status(200).json({ message: 'Admin role removed; user remains a member' });
  } catch (error) {
    console.error('removeAdmin error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// DELETE /api/communities/:communityId/members/:userId — owner or admin only
const removeMember = async (req, res) => {
  try {
    const { communityId, userId } = req.params;

    // Cannot remove the owner
    const community = req.community;
    if (community.owner_id === userId) {
      return res.status(400).json({ message: 'Cannot remove the community owner' });
    }

    const { error } = await supabase
      .from('community_roles')
      .delete()
      .eq('community_id', communityId)
      .eq('user_id', userId);

    if (error) {
      console.error('removeMember DB error:', error.message);
      return res.status(500).json({ message: 'Failed to remove member' });
    }

    return res.status(200).json({ message: 'User removed from community' });
  } catch (error) {
    console.error('removeMember error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// DELETE /api/communities/:communityId/leave — authenticated user leaves
const leaveCommunity = async (req, res) => {
  try {
    const { communityId } = req.params;
    const userId = req.user.id;

    // Owner cannot leave — they must delete or transfer ownership first
    const { data: community } = await supabase
      .from('communities')
      .select('owner_id')
      .eq('id', communityId)
      .single();

    if (!community) {
      return res.status(404).json({ message: 'Community not found' });
    }

    if (community.owner_id === userId) {
      return res.status(400).json({ message: 'Owner cannot leave. Delete the community instead.' });
    }

    const { error } = await supabase
      .from('community_roles')
      .delete()
      .eq('community_id', communityId)
      .eq('user_id', userId);

    if (error) {
      console.error('leaveCommunity DB error:', error.message);
      return res.status(500).json({ message: 'Failed to leave community' });
    }

    return res.status(200).json({ message: 'You have left the community' });
  } catch (error) {
    console.error('leaveCommunity error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// GET /api/communities/:communityId
const getCommunityDetails = async (req, res) => {
  try {
    const { communityId } = req.params;

    // 1. Fetch community row
    const { data: community, error: commError } = await supabase
      .from('communities')
      .select('id, name, description, owner_id, avatar_url, created_at')
      .eq('id', communityId)
      .single();

    if (commError || !community) {
      return res.status(404).json({ message: 'Community not found' });
    }

    // 2. Fetch all member roles for this community
    const { data: roles, error: rolesError } = await supabase
      .from('community_roles')
      .select('user_id, role')
      .eq('community_id', communityId);

    if (rolesError) {
      console.error('getCommunityDetails roles error:', rolesError.message);
      return res.status(500).json({ message: 'Failed to fetch members' });
    }

    // 3. Batch-fetch user details
    const userIds = (roles || []).map((r) => r.user_id);
    let usersMap = {};

    if (userIds.length > 0) {
      const { data: users, error: usersError } = await supabase
        .from('users')
        .select('id, name, email, avatar_url')
        .in('id', userIds);

      if (usersError) {
        console.error('getCommunityDetails users error:', usersError.message);
      } else {
        usersMap = Object.fromEntries((users || []).map((u) => [u.id, u]));
      }
    }

    // 4. Build members array
    const members = (roles || []).map((r) => {
      const user = usersMap[r.user_id];
      return {
        id: r.user_id,
        name: user?.name || null,
        email: user?.email || null,
        avatar_url: user?.avatar_url || null,
        role: r.role,
      };
    });

    // 5. Count online members via Socket.io room
    const io = req.app.get('io');
    const room = io?.sockets?.adapter?.rooms?.get(communityId);
    const onlineUserIds = new Set();
    if (room) {
      for (const socketId of room) {
        const socket = io.sockets.sockets.get(socketId);
        if (socket?.user?.id) onlineUserIds.add(socket.user.id);
      }
    }

    return res.status(200).json({
      id: community.id,
      name: community.name,
      description: community.description,
      owner_id: community.owner_id,
      avatar_url: community.avatar_url || null,
      created_at: community.created_at,
      total_members: members.length,
      online_members: onlineUserIds.size,
      members,
    });
  } catch (error) {
    console.error('getCommunityDetails error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// PATCH /api/communities/:communityId
const updateCommunity = async (req, res) => {
  try {
    const { communityId } = req.params;
    const { name, description } = req.body;
    const rawWords = req.body.restricted_words;

    if (!name && description === undefined && rawWords === undefined && !req.file) {
      return res.status(400).json({ message: 'At least one field (name, description, restricted_words, avatar) is required' });
    }

    // Build update payload with only provided fields
    const updates = {};
    if (name !== undefined) updates.name = name;
    if (description !== undefined) updates.description = description;
    const restricted_words = rawWords !== undefined
      ? (Array.isArray(rawWords) ? rawWords : JSON.parse(rawWords))
      : undefined;
    if (restricted_words !== undefined) updates.restricted_words = restricted_words;

    // Regenerate grammar whenever description or restricted_words change
    if (description !== undefined || restricted_words !== undefined) {
      try {
        // Fetch current community values to fill in any missing fields
        const { data: current } = await supabase
          .from('communities')
          .select('description, restricted_words')
          .eq('id', communityId)
          .single();

        const grammarDesc = description !== undefined ? description : (current?.description || '');
        const grammarWords = updates.restricted_words !== undefined
          ? updates.restricted_words
          : (current?.restricted_words || []);

        updates.grammar = await generateCommunityGrammar(grammarDesc, grammarWords);
      } catch (grammarError) {
        console.error('Grammar regeneration failed (proceeding without):', grammarError.message);
      }
    }

    const { data: community, error } = await supabase
      .from('communities')
      .update(updates)
      .eq('id', communityId)
      .select()
      .single();

    if (error) {
      console.error('updateCommunity DB error:', error.message);
      return res.status(500).json({ message: 'Failed to update community' });
    }

    // Upload new avatar if provided
    if (req.file) {
      try {
        const ext = path.extname(req.file.originalname) || '.jpg';
        const avatar_url = await uploadToSupabase(BUCKET_COMMUNITIES, `${communityId}${ext}`, req.file.buffer, req.file.mimetype);
        await supabase.from('communities').update({ avatar_url }).eq('id', communityId);
        community.avatar_url = avatar_url;
      } catch (uploadErr) {
        console.error('Community avatar update failed (proceeding without):', uploadErr.message);
      }
    }

    return res.status(200).json(community);
  } catch (error) {
    console.error('updateCommunity error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

module.exports = {
  createCommunity,
  getAllCommunities,
  getUserCommunities,
  addAdmin,
  joinCommunity,
  getCommunityMessages,
  sendMessage,
  deleteCommunity,
  deleteMessage,
  removeAdmin,
  removeMember,
  leaveCommunity,
  getCommunityDetails,
  updateCommunity,
};
