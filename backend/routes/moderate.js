const express = require("express");
const router = express.Router();
const { moderateMessage } = require("../services/moderationService");

/**
 * POST /api/moderate
 *
 * Body:
 *   message  (string, required) — the message to check
 *   grammar  (string, required) — the admin-defined group context / topic
 *
 * Returns the per-rule moderation results, overall status code,
 * and (if rejected) a polite suggestion.
 */
router.post("/", async (req, res) => {
  try {
    const { message, grammar } = req.body;

    // ── Validate inputs ──────────────────────────────────────
    if (!message || typeof message !== "string" || !message.trim()) {
      return res.status(400).json({
        error: "Missing or empty 'message' field.",
      });
    }

    if (!grammar || typeof grammar !== "string" || !grammar.trim()) {
      return res.status(400).json({
        error: "Missing or empty 'grammar' field. Provide the group topic / context.",
      });
    }

    // ── Run moderation ───────────────────────────────────────
    const result = await moderateMessage(message.trim(), grammar.trim());

    // HTTP 200 for approved, 422 for rejected (content policy)
    const httpStatus = result.approved ? 200 : 422;

    return res.status(httpStatus).json(result);
  } catch (err) {
    console.error("Moderation route error:", err);
    return res.status(500).json({
      error: "Internal server error during moderation.",
      details: err.message,
    });
  }
});

module.exports = router;