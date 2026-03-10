const express = require('express');
const router = express.Router();
const { register, login, logout } = require('../controllers/authController');
const { protect } = require('../middleware/authMiddleware');
const upload = require('../middleware/uploadMiddleware');

// POST /api/auth/register  — multipart/form-data: name, email, password, avatar (optional)
router.post('/register', upload.single('avatar'), register);

// POST /api/auth/login
router.post('/login', login);

// POST /api/auth/logout
router.post('/logout', protect, logout);

module.exports = router;
