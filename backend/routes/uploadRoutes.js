const express = require('express');
const router = express.Router();
const { uploadUserAvatar, uploadCommunityAvatar } = require('../controllers/uploadController');
const { protect } = require('../middleware/authMiddleware');
const { isCommunityOwnerOrAdmin } = require('../middleware/roleMiddleware');
const upload = require('../middleware/uploadMiddleware');

// PATCH /api/upload/user/avatar  — authenticated user uploads their own avatar
router.patch('/user/avatar', protect, upload.single('avatar'), uploadUserAvatar);

// PATCH /api/upload/community/:communityId/avatar  — owner or admin only
router.patch(
  '/community/:communityId/avatar',
  protect,
  isCommunityOwnerOrAdmin,
  upload.single('avatar'),
  uploadCommunityAvatar
);

module.exports = router;
