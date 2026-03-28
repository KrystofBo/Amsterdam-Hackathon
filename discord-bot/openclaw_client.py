"""
OpenClaw API Client

Sends brain dumps to OpenClaw's gateway via the OpenAI-compatible
/v1/chat/completions endpoint. Maintains conversation context for
the iterative feedback loop.
"""

import aiohttp

# System prompt that instructs OpenClaw's agent to act as both
# Synthesizer and Critic. Person A will refine these prompts —
# this is the starter "God Prompt" fallback.
SYSTEM_PROMPT = """\
You are the Idea Synthesizer, a dual-agent system for hackathon teams.

You have two roles that you execute in sequence:

## Role 1: The Synthesizer
Read all the brain dump ideas from the team members below. Draft a singular, \
cohesive project pitch that honors at least one core element from EVERY team member. \
The pitch should be concrete and buildable — not vague hand-waving.

## Role 2: The Critic
After drafting the pitch, critically evaluate it and produce an Evaluation Matrix.

## Output Format
Always respond in this EXACT format:

## 🧠 Synthesized Project Concept
**Project Name:** [A catchy name]

**Elevator Pitch:** [2-3 sentences describing the project]

**Core Features:**
- [Feature 1 — note which team member's idea this comes from]
- [Feature 2 — note which team member's idea this comes from]
- [Feature 3 — note which team member's idea this comes from]

**Tech Stack Suggestion:** [Brief recommendation]

---

## 📊 Evaluation Matrix

| Metric | Score | Reasoning |
|--------|-------|-----------|
| Novelty | X/10 | [Is there a unique twist?] |
| Technical Difficulty | X/10 | [How hard to build in a hackathon?] |
| Inclusivity | X% | [Did every team member's idea make it in?] |

**⚠️ Why It Might Fail:** [One sentence — the single biggest risk]

---

## Rules
- Always include something from EVERY contributor. If you can't integrate an idea directly, \
find a creative way to incorporate its spirit.
- Be brutally honest in the Evaluation Matrix — sugar-coating helps nobody.
- Technical Difficulty should be calibrated for a hackathon (6-hour sprint). \
A score of 7+ means "you probably won't finish this."
- When receiving feedback, adjust the EXISTING concept — don't start from scratch. \
Show what changed.
"""


class OpenClawClient:
    def __init__(self, base_url: str, token: str, agent_id: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.agent_id = agent_id

    async def synthesize(
        self,
        brain_dumps_text: str,
        conversation_history: list[dict],
        project_id: str = "",
        project_name: str = "",
    ) -> str:
        """
        Send brain dumps + conversation history to OpenClaw and get
        the synthesized pitch + evaluation matrix back.

        Each project_id (channel) gets its own system prompt context so
        OpenClaw treats them as completely separate conversations.

        For the first call, conversation_history is empty.
        For feedback rounds, it contains the prior synthesis + user feedback.
        """
        # Inject project identity into the system prompt so OpenClaw's
        # memory layer never mixes context between channels/projects
        project_context = (
            f"\n\n## Project Context\n"
            f"Project ID: {project_id}\n"
            f"Project Name: {project_name}\n"
            f"This is an isolated project session. Only consider ideas and "
            f"feedback from this specific project. Do not reference or mix in "
            f"context from any other project.\n"
        )
        messages = [{"role": "system", "content": SYSTEM_PROMPT + project_context}]

        if not conversation_history:
            # First synthesis — send the raw brain dumps
            messages.append({
                "role": "user",
                "content": (
                    f"[Project: {project_name}] "
                    "Here are the brain dumps from our team. "
                    "Please synthesize them into a unified project pitch "
                    "and score it with the Evaluation Matrix.\n\n"
                    f"{brain_dumps_text}"
                ),
            })
        else:
            # Feedback loop — include full conversation so the agent
            # can see prior synthesis and adjust based on new feedback
            messages.extend(conversation_history)

        payload = {
            "model": f"openclaw:{self.agent_id}",
            "messages": messages,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(
                        f"OpenClaw returned {resp.status}: {error_text}"
                    )
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
