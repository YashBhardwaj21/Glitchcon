const supabase = require('../config/db');
const path = require('path');
const { uploadToSupabase, BUCKET_USERS } = require('./uploadController');

// POST /api/auth/register
const register = async (req, res) => {
  try {
    const { name, email, password } = req.body;

    if (!name || !email || !password) {
      return res.status(400).json({ message: 'All fields are required' });
    }

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { name },
      },
    });

    if (error) {
      return res.status(400).json({ message: error.message });
    }

    const userId = data.user.id;

    // Upload avatar to Supabase Storage if provided
    let avatar_url = null;
    if (req.file) {
      try {
        const ext = path.extname(req.file.originalname) || '.jpg';
        avatar_url = await uploadToSupabase(BUCKET_USERS, `${userId}${ext}`, req.file.buffer, req.file.mimetype);
      } catch (uploadErr) {
        console.error('Avatar upload failed (proceeding without):', uploadErr.message);
      }
    }

    // Persist name + avatar_url to public.users
    await supabase.from('users').upsert({ id: userId, name, email, avatar_url });

    return res.status(201).json({
      id: userId,
      email: data.user.email,
      name: data.user.user_metadata?.name,
      avatar_url,
      token: data.session?.access_token ?? null,
    });
  } catch (error) {
    console.error('register error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// POST /api/auth/login
const login = async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ message: 'Email and password are required' });
    }

    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      return res.status(401).json({ message: error.message });
    }

    // Fetch avatar_url from public.users
    const { data: profile } = await supabase
      .from('users')
      .select('name, avatar_url')
      .eq('id', data.user.id)
      .single();

    return res.status(200).json({
      id: data.user.id,
      email: data.user.email,
      name: profile?.name || data.user.user_metadata?.name,
      avatar_url: profile?.avatar_url || null,
      token: data.session.access_token,
    });
  } catch (error) {
    console.error('login error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

// POST /api/auth/logout
const logout = async (req, res) => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(400).json({ message: 'No token provided' });
    }

    const { error } = await supabase.auth.signOut();

    if (error) {
      return res.status(500).json({ message: error.message });
    }

    return res.status(200).json({ message: 'Logged out successfully' });
  } catch (error) {
    console.error('logout error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

module.exports = { register, login, logout };

