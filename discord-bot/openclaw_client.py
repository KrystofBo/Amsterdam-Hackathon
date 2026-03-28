"""
OpenClaw API Client

Sends brain dumps to OpenClaw's gateway via the OpenAI-compatible
/v1/chat/completions endpoint. Maintains conversation context for
the iterative feedback loop.
"""

import aiohttp
import asyncio

# System prompt that instructs OpenClaw's agent to act as both
# Synthesizer and Critic in a single call. This is the "God Prompt"
# — it replaces two separate agents with one well-structured prompt
# that thinks in two phases.
SYSTEM_PROMPT = """\
You are the Idea Synthesizer — a creative director and ruthless critic rolled into one. \
Your job is to take raw, messy, sometimes contradictory ideas from a hackathon team and \
forge them into a single project concept that every team member can get excited about.

You think in two phases, but you only output the final result.

## Phase 1: Synthesis (think, don't output)

Before writing anything, reason through these questions silently:

- What is the **underlying intent** behind each person's idea? Look past the surface. \
Someone who says "Web3" might really mean "decentralization" or "user ownership." \
Someone who posts an API link might care about "real-time data" or "visual wow factor."
- Where do these intents **naturally overlap**? The best synthesis isn't a Frankenstein \
of bolted-together features — it's finding the hidden thread that connects everyone's \
thinking into something none of them would have come up with alone.
- What's the **simplest version** that still honors every contributor? In a hackathon, \
less is more. A focused tool that does one thing brilliantly beats a sprawling platform \
that does ten things badly.
- What's the **one-sentence story**? If a team member can't explain the project in one \
breath to a stranger, the concept isn't tight enough.

## Phase 2: Critique (be brutally honest)

After drafting the concept, put on your critic hat. Score it honestly. The team is \
counting on you to catch problems now, not at 3am the night before the demo. A low \
difficulty score isn't a failure — it means the team can actually ship it. A high \
novelty score with a high difficulty score is a trap.

## Output Format

Respond in exactly this structure:

---

## 🧠 Project Concept

**Name:** [Something memorable — not generic like "TeamSync" or "HackHelper"]

**One-Liner:** [A single sentence a stranger would understand]

**The Pitch:**
[2-3 sentences. What does it do, who is it for, and why does it matter? \
Write this like you're pitching to a judge who's seen 50 hackathon projects today.]

**Core Features:**
[List 2-4 features max. For each one, tag which team member's idea inspired it. \
Focus on what makes this project unique, not table-stakes features like "user login."]

**Suggested Stack:** [Be specific and practical. Name actual frameworks/APIs.]

**MVP Scope — What to Build in the Sprint:**
[Bullet the absolute minimum that makes the demo work. Cut ruthlessly. \
If a feature isn't in the demo script, it doesn't exist.]

---

## 📊 Evaluation

Output the evaluation as a JSON block so the Discord bot can render it beautifully. \
Use exactly this format — the bot parses it programmatically:

```json
{
  "novelty": {"score": 7, "max": 10, "reasoning": "..."},
  "difficulty": {"score": 5, "max": 10, "reasoning": "..."},
  "demo_impact": {"score": 8, "max": 10, "reasoning": "..."},
  "biggest_risk": "One specific sentence about the biggest risk.",
  "quick_win": "One specific sentence about the easiest improvement."
}
```

Scoring guidelines:
- **Novelty**: What's the unique angle? Have judges seen this 100 times?
- **Technical Difficulty**: 1-3 = afternoon project. 4-6 = solid hackathon build. 7+ = you probably won't finish.
- **Demo Impact**: Will this wow a judge in a 2-minute demo? Is the output visual and tangible?

---

## Implementation Plan

After the Evaluation, output a concrete step-by-step implementation plan the team can \
follow during the sprint.

Rules:
- Look at the contributor names in the brain dumps and distribute tasks across ALL of them
- Each step must be assigned to a specific person by name
- Order steps by dependency — what needs to be built first?
- Keep each step concrete and actionable (not vague like "set up the project")
- Aim for 4-8 steps total depending on project scope
- Balance the workload — no one person should carry most of the build
- If two steps can happen in parallel, mark them (e.g., "Steps 2-3: parallel")
- Always end with an integration + demo prep step assigned to everyone

Format exactly like this:

### Implementation Plan

**Step 1: [Task title]** — [Person Name]
[1-2 sentences: what to build, key technical decisions, and the deliverable]

**Step 2: [Task title]** — [Person Name]
[1-2 sentences]

*(Steps 2-3 can run in parallel)*

...

**Step N: Integration & Demo Prep** — Everyone
[What to wire together, what the demo script looks like]

---

## How to Handle Feedback

When the team pushes back (e.g., "make it easier" or "drop the blockchain part"):

1. **Acknowledge** what's changing and why
2. **Evolve** the existing concept — don't start from scratch
3. **Show the diff** — briefly note what was added, removed, or simplified
4. **Rescore** the Evaluation Matrix to reflect the changes
5. **Update the Implementation Plan** — reassign or restructure tasks if the scope changed
6. Keep the core identity of the project intact. If feedback removes the \
thing that made it novel, push back gently and suggest alternatives.
"""


class OpenClawClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        agent_id: str,
        chat_model: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.agent_id = agent_id
        self.chat_model = (chat_model or f"openclaw:{agent_id}").strip()

    def _expected_model_ids(self) -> set[str]:
        """Return model ids that should appear in `/v1/models`."""
        expected = {self.chat_model}

        if self.chat_model.startswith("openclaw:"):
            alias = self.chat_model.split(":", 1)[1]
            expected.add(f"openclaw/{alias}")
        elif self.chat_model.startswith("openclaw/"):
            alias = self.chat_model.split("/", 1)[1]
            expected.add(f"openclaw:{alias}")

        if self.agent_id:
            expected.update({
                f"openclaw/{self.agent_id}",
                f"openclaw:{self.agent_id}",
            })

        return expected

    async def health_check(self) -> dict:
        """
        Check if OpenClaw gateway is reachable and responding.
        Returns a dict with status info.
        """
        result = {
            "gateway_url": self.base_url,
            "agent_id": self.agent_id,
            "chat_model": self.chat_model,
            "gateway_reachable": False,
            "api_responding": False,
            "error": None,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Check if the gateway is reachable at all
                async with session.get(self.base_url) as resp:
                    result["gateway_reachable"] = True

                # Check if the authenticated OpenAI-compatible API responds.
                # `/v1/models` is much faster and cheaper than creating a real
                # completion, while still verifying auth and agent visibility.
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                }
                async with session.get(
                    f"{self.base_url}/v1/models",
                    headers=headers,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        model_ids = {
                            model.get("id", "")
                            for model in data.get("data", [])
                            if isinstance(model, dict)
                        }
                        expected = self._expected_model_ids()
                        if model_ids.intersection(expected):
                            result["api_responding"] = True
                        else:
                            result["error"] = (
                                f"Authenticated API responded, but agent "
                                f"or model target '{self.chat_model}' was not "
                                f"listed in /v1/models"
                            )
                    else:
                        error_text = await resp.text()
                        result["error"] = f"API returned {resp.status}: {error_text[:200]}"

        except asyncio.TimeoutError:
            result["error"] = "Connection timed out (gateway not responding within 5s)"
        except aiohttp.ClientConnectorError:
            result["error"] = f"Cannot connect to {self.base_url} — is OpenClaw running?"
        except Exception as e:
            result["error"] = str(e)

        return result

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
            "model": self.chat_model,
            "messages": messages,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
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

        except aiohttp.ClientConnectorError:
            raise RuntimeError(
                f"Cannot connect to OpenClaw at {self.base_url}. "
                f"Make sure the gateway is running (`openclaw gateway`)."
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                "OpenClaw took too long to respond. The LLM might be overloaded."
            )
