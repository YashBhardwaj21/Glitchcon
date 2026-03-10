const supabase = require('../config/db');

const protect = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ message: 'Not authorized, no token' });
    }

    const token = authHeader.split(' ')[1];

    // Verify the JWT against Supabase Auth and retrieve the user
    const { data, error } = await supabase.auth.getUser(token);

    if (error || !data.user) {
      return res.status(401).json({ message: 'Not authorized, token invalid' });
    }

    req.user = data.user; // { id, email, user_metadata, ... }
    next();
  } catch (error) {
    console.error('authMiddleware error:', error.message);
    return res.status(401).json({ message: 'Not authorized' });
  }
};

module.exports = { protect };

