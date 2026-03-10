const Groq = require('groq-sdk');

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

/**
 * Calls the Groq LLM to generate a comprehensive moderation "grammar" (system prompt)
 * tailored to a specific learning community.
 *
 * @param {string}   description         - The community's topic/description
 * @param {string[]} restrictedWordsArray - Words/phrases strictly banned in this community
 * @returns {string} - The generated grammar (system prompt for the downstream moderator)
 */
async function generateCommunityGrammar(description, restrictedWordsArray) {
  const restrictedList =
    Array.isArray(restrictedWordsArray) && restrictedWordsArray.length > 0
      ? restrictedWordsArray.map((w) => `"${w}"`).join(', ')
      : 'None specified';

  const metaPrompt = `
You are an expert prompt engineer specializing in AI content moderation systems for online learning communities.

Your task is to write a strict, production-ready "System Prompt" (referred to as the "grammar") that will be given to a downstream AI moderator LLM. This grammar will be used to evaluate messages in a learning community.

## Community Details
- Community Description / Topic: "${description}"
- Strictly Prohibited Words / Phrases: [${restrictedList}]

## Instructions for Writing the Grammar
The grammar you write MUST enforce ALL of the following rules:

1. **Respectful Communication**: Messages containing abusive, vulgar, hateful, or offensive language are not allowed. Maintain a professional and respectful tone.
2. **No Personal or Sensitive Information**: Do not share phone numbers, email addresses, home addresses, government IDs, bank details, passwords, OTPs, API keys, or any confidential information.
3. **No Political or Religious Discussions**: Political opinions, election-related topics, or religious debates are outside the scope of this learning community.
4. **No Promotions or Advertising**: Self-promotion, product marketing, referral links, affiliate links, brand promotions, or negative marketing about platforms are not allowed.
5. **Stay On Topic**: Discussions must be relevant to the community's topic as described above. Off-topic subjects such as unrelated technologies, social media, cinema, or entertainment are not permitted. Everything relevant to the community topic (for example, if it is software development, all related sub-domains like app development, DevOps, and system design are permitted) must be allowed.
6. **No Financial or Gambling Content**: Investment advice, trading tips, crypto discussions, betting, or gambling-related topics are prohibited.
7. **No Illegal or Unsafe Content**: Discussions about pirated software, hacking, exam malpractice, illegal activities, or unsafe practices are strictly prohibited.
8. **No Spam or Low-Quality Messages**: Repeated messages, excessive emojis, copy-paste content, or messages with no meaningful learning value will be blocked.
9. **AI Moderation Feedback**: If a message violates any guideline, the AI moderator must block it and provide a polite, constructive explanation or suggestion to help the user refine their message.
10. **Moderation Philosophy & Admin Control**: Moderation is preventive and educational, not punitive. Admins can dynamically update rules, keywords, and topic boundaries through the admin panel without code changes.
11. **Restricted Words Enforcement**: The following words/phrases are explicitly prohibited in this community and must always be flagged regardless of context: [${restrictedList}]. Any message containing even one of these must be rejected immediately.

## Strict Topic Enforcement (CRITICAL)
This community is EXCLUSIVELY about: "${description}".

You MUST apply STRICT and NARROW topic enforcement:
- ONLY messages that are DIRECTLY and SPECIFICALLY about this exact topic are permitted.
- Do NOT allow broader, adjacent, or parent domains. For example:
  - If the topic is "Machine Learning", do NOT allow general software engineering, web development, or even general AI topics unless they are directly applied to ML.
  - If the topic is "Geopolitics", do NOT allow local politics, domestic elections, or general history unless they directly relate to international geopolitical dynamics.
  - If the topic is "React.js", do NOT allow general JavaScript, Node.js, or other frontend frameworks.
- When in doubt, REJECT the message for being off-topic.
- Explicitly list in the grammar what SUB-TOPICS are permitted (derived strictly from the description) and what broader or adjacent domains are NOT permitted.

## Critical Output Requirement
The grammar you write MUST include a section that commands the downstream moderation LLM to evaluate every message and respond STRICTLY as a JSON object in the following format, with absolutely no markdown, code fences, or extra text:

If APPROVED:
{ "isAllowed": true, "reason": null }

If REJECTED:
{ "isAllowed": false, "reason": "A polite, one-sentence explanation of why the message was blocked and how to improve it." }

Now write the complete grammar (system prompt) for this community's AI moderator.
`;

  const completion = await groq.chat.completions.create({
    messages: [
      {
        role: 'system',
        content:
          'You are an expert prompt engineer. Write clear, strict, and production-ready system prompts for AI content moderation. Return only the grammar text with no additional commentary.',
      },
      {
        role: 'user',
        content: metaPrompt,
      },
    ],
    model: 'llama-3.3-70b-versatile',
    temperature: 0.3,
  });

  const grammar = completion.choices[0]?.message?.content?.trim();

  if (!grammar) {
    throw new Error('Groq returned an empty grammar response');
  }

  return grammar;
}

module.exports = { generateCommunityGrammar };
