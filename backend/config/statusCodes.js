/**
 * Moderation Status Codes
 *
 * Each code maps to one of the 10 moderation rules.
 * M200 = message approved (matches grammar context).
 * M400 = generic / catch-all moderation failure.
 */

const STATUS_CODES = {
  // ── Violation codes (one per rule) ──────────────────────────
  M100: {
    code: "M100",
    rule: "Respectful Communication",
    description:
      "Messages containing abusive, vulgar, hateful, or offensive language are not allowed.",
  },
  M101: {
    code: "M101",
    rule: "No Personal or Sensitive Information",
    description:
      "Do not share phone numbers, email addresses, home addresses, government IDs, bank details, passwords, OTPs, API keys, or any confidential information.",
  },
  M102: {
    code: "M102",
    rule: "No Political or Religious Discussions",
    description:
      "Political opinions, election-related topics, or religious debates are outside the scope of this learning community.",
  },
  M103: {
    code: "M103",
    rule: "No Promotions or Advertising",
    description:
      "Self-promotion, product marketing, referral links, affiliate links, brand promotions, or negative marketing about platforms are not allowed.",
  },
  M104: {
    code: "M104",
    rule: "Stay On Topic",
    description:
      "Discussions must be relevant to the learning group's topic. Off-topic subjects are not permitted.",
  },
  M105: {
    code: "M105",
    rule: "No Financial or Gambling Content",
    description:
      "Investment advice, trading tips, crypto discussions, betting, or gambling-related topics are prohibited.",
  },
  M106: {
    code: "M106",
    rule: "No Illegal or Unsafe Content",
    description:
      "Discussions about pirated software, hacking, exam malpractice, illegal activities, or unsafe practices are strictly prohibited.",
  },
  M107: {
    code: "M107",
    rule: "No Spam or Low-Quality Messages",
    description:
      "Repeated messages, excessive emojis, copy-paste content, or messages with no meaningful learning value will be blocked.",
  },
  M108: {
    code: "M108",
    rule: "AI Moderation Feedback",
    description:
      "If a message violates guidelines, the AI moderator blocks it and provides a polite explanation or suggestion.",
  },
  M109: {
    code: "M109",
    rule: "Moderation Philosophy & Admin Control",
    description:
      "Moderation is preventive and educational, not punitive. Admins can dynamically update rules.",
  },

  // ── Success / failure roll-ups ──────────────────────────────
  M200: {
    code: "M200",
    rule: "Approved",
    description: "Message approved — it matches the grammar context and passes all rules.",
  },
  M400: {
    code: "M400",
    rule: "Rejected",
    description: "Message rejected — one or more moderation rules were violated.",
  },
};

module.exports = STATUS_CODES;