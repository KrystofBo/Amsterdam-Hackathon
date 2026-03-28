"""
Team Brain Dump Store

Collects and stores brain dump messages from multiple users per channel.
Each channel acts as a separate "project room" — all messages in that channel
are grouped together and tagged by the user who sent them. Projects are fully
isolated: brain dumps, conversation history, and project names are all scoped
per channel.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BrainDump:
    user_id: int
    username: str
    content: str
    timestamp: datetime


class TeamStore:
    def __init__(self):
        # channel_id -> list of BrainDump entries
        self._dumps: dict[int, list[BrainDump]] = {}
        # channel_id -> list of previous synthesis conversation turns
        # Each turn is {"role": "assistant"|"user", "content": str}
        self._conversation_history: dict[int, list[dict]] = {}
        # channel_id -> project name
        self._project_names: dict[int, str] = {}
        # channel_id -> channel name (for display in !projects)
        self._channel_names: dict[int, str] = {}

    def set_project_name(self, channel_id: int, name: str, channel_name: str = ""):
        """Set a project name for a channel."""
        self._project_names[channel_id] = name
        if channel_name:
            self._channel_names[channel_id] = channel_name

    def get_project_name(self, channel_id: int) -> str:
        """Get the project name for a channel, or a default."""
        return self._project_names.get(channel_id, f"project-{channel_id}")

    def add_dump(self, channel_id: int, user_id: int, username: str, content: str, channel_name: str = ""):
        """Store a brain dump tagged by user."""
        if channel_id not in self._dumps:
            self._dumps[channel_id] = []
        if channel_name:
            self._channel_names[channel_id] = channel_name
        self._dumps[channel_id].append(BrainDump(
            user_id=user_id,
            username=username,
            content=content,
            timestamp=datetime.now(),
        ))

    def get_dumps(self, channel_id: int) -> list[BrainDump]:
        """Get all brain dumps for a channel."""
        return self._dumps.get(channel_id, [])

    def get_formatted_dumps(self, channel_id: int) -> str:
        """Format all brain dumps for sending to the agent pipeline."""
        dumps = self.get_dumps(channel_id)
        if not dumps:
            return ""

        # Group by user
        by_user: dict[str, list[str]] = {}
        for d in dumps:
            by_user.setdefault(d.username, []).append(d.content)

        lines = []
        for username, ideas in by_user.items():
            lines.append(f"**{username}**:")
            for idea in ideas:
                lines.append(f"  - {idea}")
        return "\n".join(lines)

    def get_contributor_names(self, channel_id: int) -> list[str]:
        """Get unique contributor names for a channel."""
        dumps = self.get_dumps(channel_id)
        seen = set()
        names = []
        for d in dumps:
            if d.username not in seen:
                seen.add(d.username)
                names.append(d.username)
        return names

    def clear(self, channel_id: int):
        """Clear all brain dumps and conversation history for a channel."""
        self._dumps.pop(channel_id, None)
        self._conversation_history.pop(channel_id, None)
        self._project_names.pop(channel_id, None)
        self._channel_names.pop(channel_id, None)

    def get_conversation_history(self, channel_id: int) -> list[dict]:
        """Get the synthesis conversation history for feedback loop."""
        return self._conversation_history.get(channel_id, [])

    def add_conversation_turn(self, channel_id: int, role: str, content: str):
        """Add a turn to the conversation history (for feedback loop)."""
        if channel_id not in self._conversation_history:
            self._conversation_history[channel_id] = []
        self._conversation_history[channel_id].append({
            "role": role,
            "content": content,
        })

    def has_synthesis(self, channel_id: int) -> bool:
        """Check if a synthesis has been done (conversation history exists)."""
        return bool(self._conversation_history.get(channel_id))

    def status(self, channel_id: int) -> dict:
        """Get status summary for a channel."""
        dumps = self.get_dumps(channel_id)
        return {
            "project_name": self.get_project_name(channel_id),
            "total_dumps": len(dumps),
            "contributors": self.get_contributor_names(channel_id),
            "has_synthesis": self.has_synthesis(channel_id),
            "feedback_rounds": max(0, len(self.get_conversation_history(channel_id)) // 2 - 1),
        }

    def all_projects(self) -> list[dict]:
        """List all active projects across all channels."""
        # A channel is "active" if it has dumps or a project name set
        active_channel_ids = set(self._dumps.keys()) | set(self._project_names.keys())
        projects = []
        for cid in active_channel_ids:
            projects.append({
                "channel_id": cid,
                "channel_name": self._channel_names.get(cid, "unknown"),
                "project_name": self.get_project_name(cid),
                "total_dumps": len(self.get_dumps(cid)),
                "contributors": self.get_contributor_names(cid),
                "has_synthesis": self.has_synthesis(cid),
                "feedback_rounds": max(0, len(self.get_conversation_history(cid)) // 2 - 1),
            })
        return projects
