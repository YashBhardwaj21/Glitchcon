const Groq = require("groq-sdk");

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

/**
 * Fallback system prompt used when no community grammar has been generated yet.
 */
const FALLBACK_SYSTEM_PROMPT = `
You are a strict AI content moderator for an online learning community.
Your job is to evaluate whether a message is appropriate and on-topic.

Block messages that:
- Contain abusive, offensive, or hateful language
- Share personal or sensitive information
- Discuss politics, religion, promotions, or advertising
- Are off-topic, spam, or low-quality
- Contain illegal or unsafe content

You MUST respond with ONLY valid JSON, no markdown, no code fences:
If APPROVED: { "isAllowed": true, "reason": null }
If REJECTED: { "isAllowed": false, "reason": "Polite one-sentence explanation and suggestion." }
`;

/**
 * Moderate a message using the community's stored grammar as the system prompt.
 * The grammar already contains all rules and instructs the LLM to return
 * { isAllowed: boolean, reason: string|null }.
 *
 * @param {string} message  — the message to moderate
 * @param {string} grammar  — the community's generated system prompt (grammar)
 * @returns {{ approved: boolean, reason: string|null }}
 */
const JSON_ENFORCEMENT = `

CRITICAL INSTRUCTION — OUTPUT FORMAT:
You are a content moderator. Your ONLY job is to evaluate the message and output a decision.
You MUST respond with ONLY a raw JSON object. Do NOT write any explanation, conversation, questions, or text outside the JSON.
Do NOT ask the user anything. Do NOT engage with the message content conversationally.

If the message is allowed: {"isAllowed":true,"reason":null}
If the message is blocked: {"isAllowed":false,"reason":"One-sentence polite explanation of why it was blocked and how to fix it."}
`;

async function moderateMessage(message, grammar) {
  const basePrompt = (grammar && grammar.trim().length > 0)
    ? grammar
    : FALLBACK_SYSTEM_PROMPT;

  const systemPrompt = basePrompt + JSON_ENFORCEMENT;

  const chatCompletion = await groq.chat.completions.create({
    messages: [
      {
        role: "system",
        content: systemPrompt,
      },
      {
        role: "user",
        content: `Evaluate this message: "${message}"`,
      },
    ],
    model: "llama-3.3-70b-versatile",
    temperature: 0.1,
    max_tokens: 256,
  });

  let text = chatCompletion.choices[0]?.message?.content || "";

  // Strip markdown code fences if the model wraps them
  text = text.replace(/```json\s*/gi, "").replace(/```\s*/gi, "").trim();

  try {
    const parsed = JSON.parse(text);
    return {
      approved: parsed.isAllowed === true,
      reason: parsed.reason || null,
    };
  } catch (parseError) {
    console.error("Failed to parse LLM moderation response:", text);
    return {
      approved: false,
      reason: "Your message could not be evaluated. Please rephrase and try again.",
    };
  }
}

module.exports = { moderateMessage };