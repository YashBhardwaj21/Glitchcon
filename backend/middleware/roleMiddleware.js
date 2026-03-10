const supabase = require('../config/db');

/**
 * Verifies the authenticated user is the owner or an admin of the
 * target community by querying the `communities` and `community_roles`
 * Supabase tables.
 *
 * Expects:
 *  - req.user        populated by the `protect` middleware  (req.user.id)
 *  - req.params.communityId  present on the route
 *
 * Assumed schema:
 *  communities(id, owner_id, ...)
 *  community_roles(community_id, user_id, role)  role = 'admin' | 'member'
 */
const isCommunityOwnerOrAdmin = async (req, res, next) => {
  try {
    const { communityId } = req.params;
    const userId = req.user.id;

    // Fetch the community row
    const { data: community, error: communityError } = await supabase
      .from('communities')
      .select('*')
      .eq('id', communityId)
      .single();

    if (communityError || !community) {
      return res.status(404).json({ message: 'Community not found' });
    }

    // Owner check
    if (community.owner_id === userId) {
      req.community = community;
      return next();
    }

    // Admin check via community_roles table
    const { data: roleRow, error: roleError } = await supabase
      .from('community_roles')
      .select('role')
      .eq('community_id', communityId)
      .eq('user_id', userId)
      .eq('role', 'admin')
      .maybeSingle();

    if (roleError) {
      console.error('roleMiddleware DB error:', roleError.message);
      return res.status(500).json({ message: 'Server error' });
    }

    if (!roleRow) {
      return res.status(403).json({ message: 'Access denied: owner or admin only' });
    }

    req.community = community;
    next();
  } catch (error) {
    console.error('roleMiddleware error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

/**
 * Verifies the authenticated user is strictly the owner of the community.
 * Expects req.user and req.params.communityId.
 */
const isCommunityOwner = async (req, res, next) => {
  try {
    const { communityId } = req.params;

    const { data: community, error } = await supabase
      .from('communities')
      .select('*')
      .eq('id', communityId)
      .single();

    if (error || !community) {
      return res.status(404).json({ message: 'Community not found' });
    }

    if (community.owner_id !== req.user.id) {
      return res.status(403).json({ message: 'Access denied: owner only' });
    }

    req.community = community;
    next();
  } catch (error) {
    console.error('isCommunityOwner error:', error.message);
    return res.status(500).json({ message: 'Server error' });
  }
};

module.exports = { isCommunityOwnerOrAdmin, isCommunityOwner };

