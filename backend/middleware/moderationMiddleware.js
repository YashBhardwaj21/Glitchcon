const { moderateMessage } = require('../services/moderationService');
const STATUS_CODES = require('../config/statusCodes');
const supabase = require('../config/db');

const EXTERNAL_MODERATION_URL = 'https://commonsmodel-1.onrender.com/query';

function forwardToExternalAPI(payload) {
  fetch(EXTERNAL_MODERATION_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch((err) => console.error('External moderation API error:', err.message));
}

const moderateMessageContent = async (req, res, next) => {
  try {
    const isAudio = req.body.type === 'audio';
    // For audio messages the frontend sends the transcription to evaluate;
    // for text messages we evaluate content directly.
    const content = isAudio
      ? req.body.transcription?.trim()
      : req.body.content?.trim();

    if (!content) {
      return res.status(400).json({
        message: isAudio ? 'Transcription is required for audio messages' : 'Message content is required',
      });
    }

    const { communityId } = req.params;

    // Fetch the community's generated grammar for moderation context
    const { data: community, error } = await supabase
      .from('communities')
      .select('grammar, description')
      .eq('id', communityId)
      .single();

    const grammar = (!error && community?.grammar)
      ? community.grammar
      : (community?.description || 'General community discussion');

    const result = await moderateMessage(content, grammar);

    // Fire-and-forget: forward LLM moderation output to external API
    forwardToExternalAPI({
      community_id: communityId,
      message: content,
      approved: result.approved,
      reason: result.reason || null,
    });

    if (!result.approved) {
      return res.status(422).json({
        moderated: true,
        blocked: true,
        reason: result.reason || 'Your message was blocked. Please review the community guidelines.',
      });
    }

    next();
  } catch (err) {
    console.error('moderationMiddleware error:', err.message);
    // Fail open — if the moderation service is down, let the message through
    next();
  }
};

module.exports = { moderateMessageContent };
