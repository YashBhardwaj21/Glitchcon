const { createClient } = require('@supabase/supabase-js');
const supabase = require('../config/db');
const path = require('path');

// Use service role key for storage uploads — bypasses RLS on storage buckets
const supabaseAdmin = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

const BUCKET_USERS = 'avatars';
const BUCKET_COMMUNITIES = 'community-avatars';
const BUCKET_AUDIO = 'audio-messages';

/**
 * Upload a file buffer to a Supabase Storage bucket and return the public URL.
 */
async function uploadToSupabase(bucket, filePath, buffer, mimetype) {
  const { error } = await supabaseAdmin.storage
    .from(bucket)
    .upload(filePath, buffer, {
      contentType: mimetype,
      upsert: true, // overwrite if this user/community already has a picture
    });

  if (error) throw new Error(error.message);

  const { data } = supabaseAdmin.storage.from(bucket).getPublicUrl(filePath);
  return data.publicUrl;
}

// PATCH /api/upload/user/avatar
const uploadUserAvatar = async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: 'No image file provided' });
    }

    const ext = path.extname(req.file.originalname) || '.jpg';
    const filePath = `${req.user.id}${ext}`;

    const publicUrl = await uploadToSupabase(
      BUCKET_USERS,
      filePath,
      req.file.buffer,
      req.file.mimetype
    );

    // Save URL to public.users table
    const { error } = await supabase
      .from('users')
      .update({ avatar_url: publicUrl })
      .eq('id', req.user.id);

    if (error) {
      console.error('uploadUserAvatar DB error:', error.message);
      return res.status(500).json({ message: 'Failed to save avatar URL' });
    }

    return res.status(200).json({ avatar_url: publicUrl });
  } catch (err) {
    console.error('uploadUserAvatar error:', err.message);
    return res.status(500).json({ message: err.message || 'Server error' });
  }
};

// PATCH /api/upload/community/:communityId/avatar
const uploadCommunityAvatar = async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: 'No image file provided' });
    }

    const { communityId } = req.params;
    const ext = path.extname(req.file.originalname) || '.jpg';
    const filePath = `${communityId}${ext}`;

    const publicUrl = await uploadToSupabase(
      BUCKET_COMMUNITIES,
      filePath,
      req.file.buffer,
      req.file.mimetype
    );

    // Save URL to communities table
    const { error } = await supabase
      .from('communities')
      .update({ avatar_url: publicUrl })
      .eq('id', communityId);

    if (error) {
      console.error('uploadCommunityAvatar DB error:', error.message);
      return res.status(500).json({ message: 'Failed to save avatar URL' });
    }

    return res.status(200).json({ avatar_url: publicUrl });
  } catch (err) {
    console.error('uploadCommunityAvatar error:', err.message);
    return res.status(500).json({ message: err.message || 'Server error' });
  }
};

module.exports = { uploadUserAvatar, uploadCommunityAvatar, uploadToSupabase, BUCKET_USERS, BUCKET_COMMUNITIES, BUCKET_AUDIO };
