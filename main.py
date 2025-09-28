import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import os

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = discord.Object(id=1011467123480072214)


class Client(commands.Bot):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        try:
            synced = await self.tree.sync(guild=GUILD_ID)
            print(f"Synced {len(synced)} command(s) to the guild.")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
        update_status.start()


intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix="!", intents=intents)

fakeServerStatus = True
fakeMinecraftStatus = False

status_message = None
last_server_status = None
last_minecraft_status = None


async def get_server_status():
    # Replace this with real checks (ping, API call, etc.)
    global fakeServerStatus, fakeMinecraftStatus
    server_online = fakeServerStatus
    minecraft_online = fakeMinecraftStatus
    return server_online, minecraft_online


def build_embed(server_online: bool, minecraft_online: bool):
    embed = discord.Embed(
        title="Server Status",
        description="Current status of the servers",
    )
    embed.add_field(
        name="PC Server",
        value="🟢 Online" if server_online else f"🔴 Offline",
        inline=False,
    )
    embed.add_field(
        name="Minecraft Server",
        value="🟢 Online" if minecraft_online else f"🔴 Offline",
        inline=False,
    )
    return embed


async def refresh_status(
    interaction: discord.Interaction | None = None,
    message: discord.Message | None = None,
):
    global last_server_status, last_minecraft_status

    server_online, minecraft_online = await get_server_status()

    # only refresh if there's a change
    if (
        server_online == last_server_status
        and minecraft_online == last_minecraft_status
    ):
        return  # nothing to do

    # update globals
    last_server_status = server_online
    last_minecraft_status = minecraft_online

    embed = build_embed(server_online, minecraft_online)
    view = ControlView(server_online, minecraft_online)

    if interaction:
        # button press or slash command
        await interaction.message.edit(embed=embed, view=view)
    elif message:
        # background loop
        await message.edit(embed=embed, view=view)


async def start_pc():
    # your start-PC logic here
    global fakeServerStatus
    fakeServerStatus = True
    pass


async def shutdown_pc():
    # your shutdown-PC logic here
    global fakeServerStatus
    fakeServerStatus = False
    pass


async def restart_pc():
    # your restart-PC logic here
    pass


async def start_minecraft():
    # your start-MC logic here
    global fakeMinecraftStatus
    fakeMinecraftStatus = True
    pass


async def stop_minecraft():
    # your stop-MC logic here
    global fakeMinecraftStatus
    fakeMinecraftStatus = False
    pass


class ControlView(discord.ui.View):
    def __init__(self, server_online: bool, minecraft_online: bool):
        super().__init__(timeout=None)

        # PC button: show ON or OFF, not both
        if server_online:
            self.add_item(self.ShutdownPC())
        else:
            self.add_item(self.StartPC())

        # minecraft button
        if minecraft_online:
            self.add_item(self.StopMinecraft())
        else:
            self.add_item(self.StartMinecraft())

        # Refresh always present
        self.add_item(self.Refresh())

    class StartPC(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Turn On PC", style=discord.ButtonStyle.green)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message("Starting PC...")

            await start_pc()

            await refresh_status(interaction=interaction)

    class ShutdownPC(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Shutdown PC", style=discord.ButtonStyle.red)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message("Shutting down PC...")

            await shutdown_pc()

            await refresh_status(interaction=interaction)

    class StartMinecraft(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Start Minecraft", style=discord.ButtonStyle.green)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message("Starting Minecraft...")

            await start_minecraft()

            await refresh_status(interaction=interaction)

    class StopMinecraft(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Stop Minecraft", style=discord.ButtonStyle.red)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message("Stopping Minecraft...")

            await stop_minecraft()

            await refresh_status(interaction=interaction)

    class Refresh(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Refresh", style=discord.ButtonStyle.gray)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message("Refreshing...")
            await refresh_status(interaction=interaction)


@client.tree.command(
    name="status", description="Get the current status of the server", guild=GUILD_ID
)
async def status_command(interaction: discord.Interaction):
    global status_message, last_server_status, last_minecraft_status

    # delete the old panel if it exists
    if status_message:
        try:
            await status_message.delete()
        except discord.NotFound:
            pass  # already deleted manually

    server_online, minecraft_online = await get_server_status()
    embed = build_embed(server_online, minecraft_online)

    await interaction.response.send_message(
        embed=embed, view=ControlView(server_online, minecraft_online)
    )

    last_server_status = server_online
    last_minecraft_status = minecraft_online

    status_message = await interaction.channel.fetch_message(
        (await interaction.original_response()).id
    )


# PC command group
pc_group = app_commands.Group(name="pc", description="PC server controls")


@pc_group.command(name="start", description="Start the PC server")
async def pc_start(interaction: discord.Interaction):
    await interaction.response.send_message("Starting PC...")
    await start_pc()


@pc_group.command(name="shutdown", description="Shut down the PC server")
async def pc_shutdown(interaction: discord.Interaction):
    await interaction.response.send_message("Shutting down PC...")
    await shutdown_pc()


@pc_group.command(name="restart", description="Restart the PC server")
async def pc_restart(interaction: discord.Interaction):
    await interaction.response.send_message("Restarting PC...")
    await restart_pc()


# Minecraft command group
mc_group = app_commands.Group(name="mc", description="Minecraft server controls")


@mc_group.command(name="start", description="Start the Minecraft server")
async def mc_start(interaction: discord.Interaction):
    await interaction.response.send_message("Starting Minecraft...")
    await start_minecraft()


@mc_group.command(name="stop", description="Stop the Minecraft server")
async def mc_stop(interaction: discord.Interaction):
    await interaction.response.send_message("Stopping Minecraft...")
    await stop_minecraft()


# Register both groups
client.tree.add_command(pc_group, guild=GUILD_ID)
client.tree.add_command(mc_group, guild=GUILD_ID)


@tasks.loop(seconds=30)  # every 30s, adjust as needed
async def update_status():
    global status_message
    if status_message:
        await refresh_status(message=status_message)


client.run(DISCORD_TOKEN)
