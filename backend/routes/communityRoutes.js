const express = require('express');
const router = express.Router();
const {
  createCommunity,
  getAllCommunities,
  getUserCommunities,
  getCommunityDetails,
  addAdmin,
  joinCommunity,
  getCommunityMessages,
  sendMessage,
  deleteCommunity,
  deleteMessage,
  removeAdmin,
  removeMember,
  leaveCommunity,
  updateCommunity,
} = require('../controllers/communityController');
const { protect } = require('../middleware/authMiddleware');
const { isCommunityOwnerOrAdmin, isCommunityOwner } = require('../middleware/roleMiddleware');
const { moderateMessageContent } = require('../middleware/moderationMiddleware');
const upload = require('../middleware/uploadMiddleware');

// GET    /api/communities                              — browse all communities
router.get('/', protect, getAllCommunities);

// GET    /api/communities/me                           — communities the user has joined
router.get('/me', protect, getUserCommunities);

// POST   /api/communities  — multipart/form-data: name, description, restricted_words, avatar (optional)
router.post('/', protect, upload.single('avatar'), createCommunity);

// GET    /api/communities/:communityId                  — community details + members + online count
router.get('/:communityId', protect, getCommunityDetails);

// DELETE /api/communities/:communityId                 — owner only
router.delete('/:communityId', protect, isCommunityOwner, deleteCommunity);

// PATCH  /api/communities/:communityId                  — update community info (owner or admin only)
router.patch('/:communityId', protect, isCommunityOwnerOrAdmin, upload.single('avatar'), updateCommunity);

// POST   /api/communities/:communityId/admins          — add an admin (owner or admin only)
router.post('/:communityId/admins', protect, isCommunityOwnerOrAdmin, addAdmin);

// DELETE /api/communities/:communityId/admins/:userId  — remove admin role (owner or admin only)
router.delete('/:communityId/admins/:userId', protect, isCommunityOwnerOrAdmin, removeAdmin);

// POST   /api/communities/:communityId/join            — join a community
router.post('/:communityId/join', protect, joinCommunity);

// DELETE /api/communities/:communityId/leave           — authenticated user leaves
router.delete('/:communityId/leave', protect, leaveCommunity);

// DELETE /api/communities/:communityId/members/:userId — remove a member (owner or admin only)
router.delete('/:communityId/members/:userId', protect, isCommunityOwnerOrAdmin, removeMember);

// GET    /api/communities/:communityId/messages        — fetch last 50 messages
router.get('/:communityId/messages', protect, getCommunityMessages);

// POST   /api/communities/:communityId/messages        — send a message (moderated)
// multipart/form-data: type ('text'|'audio'), content (text) OR transcription+audio (audio)
router.post('/:communityId/messages', protect, upload.single('audio'), moderateMessageContent, sendMessage);

// DELETE /api/communities/:communityId/messages/:messageId — delete a message
router.delete('/:communityId/messages/:messageId', protect, deleteMessage);

module.exports = router;
