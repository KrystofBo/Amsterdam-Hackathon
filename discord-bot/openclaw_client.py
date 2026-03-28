"""
OpenClaw API Client

Sends brain dumps to OpenClaw's gateway via the OpenAI-compatible
/v1/chat/completions endpoint. Maintains conversation context for
the iterative feedback loop.
"""

import aiohttp
import asyncio

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
