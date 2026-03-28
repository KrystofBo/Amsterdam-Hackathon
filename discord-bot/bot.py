"""
Idea Synthesizer Discord Bot

Commands:
  !dump <idea>        — Add a brain dump to the pool
  !synthesize         — Fuse all brain dumps into a scored pitch
  !feedback <text>    — Push back on the current pitch (triggers re-synthesis)
  !project <name>     — Name this channel's project
  !projects           — List all active projects across channels
  !status             — Show how many dumps, who contributed, synthesis state
  !clear              — Wipe all dumps and conversation history for this channel
  !lobby              — Post the lobby welcome panel (create/join projects)
  !help               — Show available commands
"""

import os
import sys
import discord
from discord.ext import commands
from discord import ui
from dotenv import load_dotenv

# Unbuffer stdout so print() shows immediately in terminal
sys.stdout.reconfigure(line_buffering=True)

from team_store import TeamStore
from openclaw_client import OpenClawClient

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENCLAW_URL = os.getenv("OPENCLAW_URL", "http://localhost:18789")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_TOKEN", "")
OPENCLAW_AGENT_ID = os.getenv("OPENCLAW_AGENT_ID", "synthesizer")

# Category name where project channels are created
PROJECT_CATEGORY = os.getenv("PROJECT_CATEGORY", "PROJECTS")

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Core components
store = TeamStore()
openclaw = OpenClawClient(OPENCLAW_URL, OPENCLAW_TOKEN, OPENCLAW_AGENT_ID)


# ---------------------------------------------------------------------------
# Lobby UI: Create / Join project
# ---------------------------------------------------------------------------

class CreateProjectModal(ui.Modal, title="Create a New Project"):
    project_name = ui.TextInput(
        label="Project Name",
        placeholder="e.g. NASA Edu Game",
        min_length=2,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        name = self.project_name.value.strip()
        guild = interaction.guild

        # Find or create the PROJECTS category
        category = discord.utils.get(guild.categories, name=PROJECT_CATEGORY)
        if category is None:
            category = await guild.create_category(PROJECT_CATEGORY)

        # Create a text channel under the category
        channel_name = name.lower().replace(" ", "-")
        channel = await guild.create_text_channel(channel_name, category=category)

        # Register the project
        store.set_project_name(channel.id, name, channel_name=channel.name)

        # Post a welcome message in the new channel
        welcome = discord.Embed(
            title=f"Project: {name}",
            description=(
                f"Welcome to **{name}**! This is your team's brainstorming space.\n\n"
                "Get started by dumping your ideas:\n"
                "`!dump <your idea>`\n\n"
                "When everyone's ready, run `!synthesize` to fuse them into a scored pitch."
            ),
            color=0x2ECC71,
        )
        await channel.send(embed=welcome)

        await interaction.response.send_message(
            f"Project **{name}** created! Head over to {channel.mention}",
            ephemeral=True,
        )


class JoinProjectSelect(ui.Select):
    def __init__(self, options_list):
        super().__init__(
            placeholder="Choose a project to join...",
            options=options_list,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            await interaction.response.send_message(
                "That channel no longer exists.", ephemeral=True
            )
            return

        # Grant the user access if the channel has restricted permissions
        await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)

        await interaction.response.send_message(
            f"You've joined **{store.get_project_name(channel_id)}**! "
            f"Head over to {channel.mention}",
            ephemeral=True,
        )


class JoinProjectView(ui.View):
    def __init__(self, options_list):
        super().__init__(timeout=None)
        self.add_item(JoinProjectSelect(options_list))


class LobbyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Create Project", style=discord.ButtonStyle.green, emoji="\u2795", custom_id="lobby:create")
    async def create_project(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CreateProjectModal())

    @ui.button(label="Join Project", style=discord.ButtonStyle.blurple, emoji="\U0001f4c2", custom_id="lobby:join")
    async def join_project(self, interaction: discord.Interaction, button: ui.Button):
        # Build list of active project channels
        all_projects = store.all_projects()

        # Also scan the PROJECTS category for channels not yet in the store
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=PROJECT_CATEGORY)
        if category:
            for ch in category.text_channels:
                if not any(p["channel_id"] == ch.id for p in all_projects):
                    all_projects.append({
                        "channel_id": ch.id,
                        "channel_name": ch.name,
                        "project_name": ch.name.replace("-", " ").title(),
                        "total_dumps": 0,
                        "contributors": [],
                        "has_synthesis": False,
                        "feedback_rounds": 0,
                    })

        if not all_projects:
            await interaction.response.send_message(
                "No projects yet! Click **Create Project** to start one.",
                ephemeral=True,
            )
            return

        options = []
        for p in all_projects[:25]:  # Discord max 25 select options
            status_text = f"{p['total_dumps']} ideas"
            if p["contributors"]:
                status_text += f" from {', '.join(p['contributors'][:3])}"
            options.append(discord.SelectOption(
                label=p["project_name"][:100],
                value=str(p["channel_id"]),
                description=status_text[:100],
            ))

        view = JoinProjectView(options)
        await interaction.response.send_message(
            "Select a project to join:",
            view=view,
            ephemeral=True,
        )

# Discord has a 2000-char message limit — split long responses
MAX_MSG_LEN = 1900


def split_message(text: str) -> list[str]:
    """Split a long message into chunks that fit Discord's limit."""
    if len(text) <= MAX_MSG_LEN:
        return [text]
    chunks = []
    while text:
        if len(text) <= MAX_MSG_LEN:
            chunks.append(text)
            break
        # Try to split at a newline near the limit
        split_at = text.rfind("\n", 0, MAX_MSG_LEN)
        if split_at == -1:
            split_at = MAX_MSG_LEN
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


@bot.event
async def on_ready():
    # Register the lobby view so buttons survive bot restarts
    bot.add_view(LobbyView())
    print(f"Idea Synthesizer Bot is online as {bot.user}")
    print(f"Connected to OpenClaw at {OPENCLAW_URL}")
    print(f"Using agent: {OPENCLAW_AGENT_ID}")


@bot.command(name="lobby")
async def lobby(ctx):
    """Post the lobby panel with Create/Join project buttons."""
    embed = discord.Embed(
        title="Idea Synthesizer",
        description=(
            "Welcome! This is where hackathon teams turn chaotic ideas "
            "into focused, scored project pitches.\n\n"
            "**Create a Project** — Start a new brainstorming channel for your team\n"
            "**Join a Project** — Jump into an existing project"
        ),
        color=0x7289DA,
    )
    embed.set_footer(text="Each project gets its own channel. Ideas stay isolated.")
    await ctx.send(embed=embed, view=LobbyView())


@bot.command(name="help")
async def help_cmd(ctx):
    """Show available commands."""
    embed = discord.Embed(
        title="Idea Synthesizer Bot",
        description="Fuse your team's brain dumps into a cohesive project pitch!",
        color=0x7289DA,
    )
    embed.add_field(name="!dump <idea>", value="Add your idea to the pool", inline=False)
    embed.add_field(name="!synthesize", value="Fuse all ideas into a scored project pitch", inline=False)
    embed.add_field(name="!feedback <text>", value="Push back on the current pitch (e.g., 'make it easier to build')", inline=False)
    embed.add_field(name="!project <name>", value="Name this channel's project", inline=False)
    embed.add_field(name="!projects", value="List all active projects across channels", inline=False)
    embed.add_field(name="!status", value="See who's contributed and current state", inline=False)
    embed.add_field(name="!clear", value="Wipe all ideas and start fresh", inline=False)
    embed.add_field(name="!lobby", value="Post the lobby panel (create/join projects)", inline=False)
    embed.add_field(name="!health", value="Check if OpenClaw is connected and responding", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="project")
async def project(ctx, *, name: str):
    """Name this channel's project."""
    store.set_project_name(ctx.channel.id, name, channel_name=ctx.channel.name)
    await ctx.send(f"Project for this channel set to: **{name}**")


@bot.command(name="projects")
async def projects(ctx):
    """List all active projects across channels."""
    all_projects = store.all_projects()
    if not all_projects:
        await ctx.send("No active projects yet. Use `!dump` or `!project` in a channel to get started.")
        return

    embed = discord.Embed(
        title="All Active Projects",
        description=f"{len(all_projects)} project(s) across the server",
        color=0x9B59B6,
    )
    for p in all_projects:
        contributors = ", ".join(p["contributors"]) if p["contributors"] else "None yet"
        synthesis_status = "Synthesized" if p["has_synthesis"] else "Collecting ideas"
        feedback_info = f" ({p['feedback_rounds']} feedback rounds)" if p["feedback_rounds"] > 0 else ""
        embed.add_field(
            name=f"{p['project_name']}",
            value=(
                f"Channel: #{p['channel_name']}\n"
                f"Ideas: {p['total_dumps']} | Contributors: {contributors}\n"
                f"Status: {synthesis_status}{feedback_info}"
            ),
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.command(name="dump")
async def dump(ctx, *, idea: str):
    """Add a brain dump to the pool."""
    store.add_dump(
        channel_id=ctx.channel.id,
        user_id=ctx.author.id,
        username=ctx.author.display_name,
        content=idea,
        channel_name=ctx.channel.name,
    )
    count = len(store.get_dumps(ctx.channel.id))
    contributors = store.get_contributor_names(ctx.channel.id)
    project_name = store.get_project_name(ctx.channel.id)
    await ctx.send(
        f"**Brain dump received from {ctx.author.display_name}!** "
        f"[{project_name}] "
        f"({count} total ideas from {len(contributors)} contributor(s))"
    )


@bot.command(name="synthesize")
async def synthesize(ctx):
    """Fuse all brain dumps into a scored project pitch."""
    dumps_text = store.get_formatted_dumps(ctx.channel.id)
    if not dumps_text:
        await ctx.send("No brain dumps yet! Use `!dump <your idea>` to add ideas first.")
        return

    contributors = store.get_contributor_names(ctx.channel.id)
    project_name = store.get_project_name(ctx.channel.id)
    await ctx.send(
        f"Synthesizing ideas for **{project_name}** "
        f"from **{', '.join(contributors)}**... "
        f"This may take a moment."
    )

    try:
        history = store.get_conversation_history(ctx.channel.id)
        project_id = str(ctx.channel.id)
        result = await openclaw.synthesize(
            dumps_text,
            history,
            project_id=project_id,
            project_name=project_name,
        )

        # Store the conversation for the feedback loop
        if not history:
            store.add_conversation_turn(
                ctx.channel.id,
                "user",
                f"[Project: {project_name}] "
                f"Here are the brain dumps from our team. "
                f"Please synthesize them into a unified project pitch "
                f"and score it with the Evaluation Matrix.\n\n{dumps_text}",
            )
        store.add_conversation_turn(ctx.channel.id, "assistant", result)

        for chunk in split_message(result):
            await ctx.send(chunk)

    except Exception as e:
        await ctx.send(f"Error connecting to OpenClaw: {e}")


@bot.command(name="feedback")
async def feedback(ctx, *, text: str):
    """Push back on the current pitch — triggers a re-synthesis."""
    if not store.has_synthesis(ctx.channel.id):
        await ctx.send(
            "No synthesis yet! Run `!synthesize` first, then give feedback."
        )
        return

    project_name = store.get_project_name(ctx.channel.id)
    await ctx.send(
        f"**Feedback from {ctx.author.display_name}** [{project_name}]: {text}\n"
        f"Re-synthesizing with your constraints..."
    )

    try:
        store.add_conversation_turn(
            ctx.channel.id,
            "user",
            f"[Project: {project_name}] "
            f"Feedback from {ctx.author.display_name}: {text}",
        )

        history = store.get_conversation_history(ctx.channel.id)
        project_id = str(ctx.channel.id)
        result = await openclaw.synthesize(
            store.get_formatted_dumps(ctx.channel.id),
            history,
            project_id=project_id,
            project_name=project_name,
        )

        store.add_conversation_turn(ctx.channel.id, "assistant", result)

        for chunk in split_message(result):
            await ctx.send(chunk)

    except Exception as e:
        await ctx.send(f"Error connecting to OpenClaw: {e}")


@bot.command(name="status")
async def status(ctx):
    """Show current state of brain dumps and synthesis."""
    info = store.status(ctx.channel.id)
    embed = discord.Embed(
        title=f"Project: {info['project_name']}",
        color=0x2ECC71,
    )
    embed.add_field(
        name="Brain Dumps",
        value=str(info["total_dumps"]),
        inline=True,
    )
    embed.add_field(
        name="Contributors",
        value=", ".join(info["contributors"]) if info["contributors"] else "None yet",
        inline=True,
    )
    embed.add_field(
        name="Synthesis Done?",
        value="Yes" if info["has_synthesis"] else "Not yet",
        inline=True,
    )
    embed.add_field(
        name="Feedback Rounds",
        value=str(info["feedback_rounds"]),
        inline=True,
    )
    await ctx.send(embed=embed)


@bot.command(name="clear")
async def clear(ctx):
    """Wipe all brain dumps and conversation history."""
    store.clear(ctx.channel.id)
    await ctx.send("All brain dumps and conversation history cleared. Fresh start!")


@bot.command(name="health")
async def health(ctx):
    """Check if the OpenClaw gateway is connected and responding."""
    msg = await ctx.send("Checking OpenClaw connection...")

    result = await openclaw.health_check()

    if result["gateway_reachable"] and result["api_responding"]:
        embed = discord.Embed(
            title="OpenClaw Health Check",
            description="All systems operational!",
            color=0x2ECC71,  # green
        )
        embed.add_field(name="Gateway", value=f"`{result['gateway_url']}`", inline=False)
        embed.add_field(name="Agent", value=f"`{result['agent_id']}`", inline=True)
        embed.add_field(name="Gateway Reachable", value="Yes", inline=True)
        embed.add_field(name="API Responding", value="Yes", inline=True)
    else:
        embed = discord.Embed(
            title="OpenClaw Health Check",
            description="Connection issues detected",
            color=0xE74C3C,  # red
        )
        embed.add_field(name="Gateway", value=f"`{result['gateway_url']}`", inline=False)
        embed.add_field(name="Agent", value=f"`{result['agent_id']}`", inline=True)
        embed.add_field(
            name="Gateway Reachable",
            value="Yes" if result["gateway_reachable"] else "No",
            inline=True,
        )
        embed.add_field(
            name="API Responding",
            value="Yes" if result["api_responding"] else "No",
            inline=True,
        )
        if result["error"]:
            embed.add_field(name="Error", value=result["error"][:1024], inline=False)

        # Helpful troubleshooting tips
        tips = []
        if not result["gateway_reachable"]:
            tips.append("Make sure OpenClaw is running: `openclaw gateway`")
            tips.append(f"Verify the URL in `.env`: `OPENCLAW_URL={result['gateway_url']}`")
        elif not result["api_responding"]:
            tips.append("Gateway is up but the agent isn't responding")
            tips.append(f"Check that agent `{result['agent_id']}` exists: `openclaw agents list`")
            tips.append("Verify `OPENCLAW_TOKEN` in `.env` is correct")
        if tips:
            embed.add_field(name="Troubleshooting", value="\n".join(f"• {t}" for t in tips), inline=False)

    await msg.edit(content=None, embed=embed)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("ERROR: Set DISCORD_TOKEN in your .env file")
        print("See .env.example for the required variables")
        exit(1)
    bot.run(DISCORD_TOKEN)
