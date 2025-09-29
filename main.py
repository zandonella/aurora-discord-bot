import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import os
import asyncio
import aiohttp
from mcstatus import JavaServer

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PC_IP = os.getenv("PC_IP")
MAC_ADDRESS = os.getenv("MAC_ADDRESS")
MC_PORT = int(os.getenv("MC_PORT", 25565))
WOL_API_IP = os.getenv("WOL_API_IP")
WOL_API_PORT = int(os.getenv("WOL_API_PORT", 8000))
SERVER_API_IP = os.getenv("SERVER_API_IP")
SERVER_API_PORT = int(os.getenv("SERVER_API_PORT", 6000))
GUILD_ID = discord.Object(id=1011467123480072214)

SERVER_URL = f"http://{SERVER_API_IP}:{SERVER_API_PORT}"

SERVERS = os.getenv("SERVERS")


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

status_message = None
last_status_data = None


async def get_server_status():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SERVER_URL}/status", timeout=5) as resp:
                if resp.status != 200:
                    raise Exception(
                        f"Bad status: {resp.status}"
                    )  # API didn't respond OK
                return await resp.json()
    except Exception as e:
        print(f"Error fetching server status: {e}")
        return {"server": "offline", "services": {}}


def build_embed(data: dict):
    embed = discord.Embed(
        title="Server Status",
        description="Current status of the servers",
    )

    server_status = "🟢 Online" if data.get("server") == "online" else "🔴 Offline"
    embed.add_field(name="Server", value=server_status, inline=False)

    services = data.get("services", {})
    for name, info in services.items():
        if info.get("health") == "healthy":
            val = (
                f"🟢 Online\n"
                f"Players: {info.get('players', 0)}/{info.get('max_players', 0)}\n"
            )
        elif info.get("health") == "starting":
            val = (
                f"🟡 Starting...\n"
                f"Players: {info.get('players', 0)}/{info.get('max_players', 0)}\n"
            )
        else:
            val = (
                f"🔴 Offline\n"
                f"Players: {info.get('players', 0)}/{info.get('max_players', 0)}\n"
            )
        embed.add_field(name=name, value=val, inline=False)

    return embed


async def refresh_status(
    interaction: discord.Interaction | None = None,
    message: discord.Message | None = None,
):
    global last_status_data, status_message

    data = await get_server_status()
    if not data:
        return

    # only refresh if there's a change
    if data == last_status_data:
        return

    # update globals
    last_status_data = data
    embed = build_embed(data)
    view = ControlView(data)

    target_message = None
    if interaction and interaction.message:
        target_message = interaction.message
    elif message:
        target_message = message
    elif status_message:
        target_message = status_message

    if target_message:
        try:
            await target_message.edit(embed=embed, view=view)
            status_message = target_message
        except discord.NotFound:
            status_message = None


async def start_pc():
    async with aiohttp.ClientSession() as session:
        async with session.post(f"http://{WOL_API_IP}:{WOL_API_PORT}/wake") as resp:
            return resp.status, await resp.json()


async def shutdown_pc():
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVER_URL}/pc/shutdown") as resp:
            return resp.status, await resp.json()


async def restart_pc():
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVER_URL}/pc/reboot") as resp:
            return resp.status, await resp.json()


async def start_minecraft(name: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVER_URL}/mc/start?name={name}") as resp:
            return resp.status, await resp.json()


async def stop_minecraft(name: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVER_URL}/mc/stop?name={name}") as resp:
            return resp.status, await resp.json()


async def restart_minecraft(name: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVER_URL}/mc/restart?name={name}") as resp:
            return resp.status, await resp.json()


class ControlView(discord.ui.View):
    def __init__(self, status_data: dict):
        super().__init__(timeout=None)

        # PC button: show ON or OFF, not both
        if status_data.get("server") == "online":
            self.add_item(self.ShutdownPC())
        else:
            self.add_item(self.StartPC())

        # minecraft button
        for name, info in status_data.get("services", {}).items():
            if info.get("health") != "unhealthy":
                self.add_item(self.StopMinecraft(name))
            else:
                self.add_item(self.StartMinecraft(name))

        # Refresh always present
        self.add_item(self.Refresh())

    class StartPC(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Turn On PC", style=discord.ButtonStyle.green)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()

            status, data = await start_pc()
            if status != 200:
                await interaction.followup.send(f"❌ Failed: {data}")

            await refresh_status(interaction=interaction)

    class ShutdownPC(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Shutdown PC", style=discord.ButtonStyle.red)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()

            status, data = await shutdown_pc()
            if status != 200:
                await interaction.followup.send(f"❌ Failed: {data}")

            await refresh_status(interaction=interaction)

    class StartMinecraft(discord.ui.Button):
        def __init__(self, server_name: str):
            super().__init__(
                label=f"Start {server_name}", style=discord.ButtonStyle.green
            )
            self.server_name = server_name

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()

            status, data = await start_minecraft(self.server_name)
            if status != 200:
                await interaction.followup.send(f"❌ Failed: {data}")

            await refresh_status(interaction=interaction)

    class StopMinecraft(discord.ui.Button):
        def __init__(self, server_name: str):
            super().__init__(label=f"Stop {server_name}", style=discord.ButtonStyle.red)
            self.server_name = server_name

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()

            status, data = await stop_minecraft(self.server_name)
            if status != 200:
                await interaction.followup.send(f"❌ Failed: {data}")

            await refresh_status(interaction=interaction)

    class Refresh(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Refresh", style=discord.ButtonStyle.gray)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            await refresh_status(interaction=interaction)


@client.tree.command(
    name="status", description="Get the current status of the server", guild=GUILD_ID
)
async def status_command(interaction: discord.Interaction):
    global status_message, last_status_data

    # delete the old panel if it exists
    if status_message:
        try:
            await status_message.delete()
        except discord.NotFound:
            pass  # already deleted manually

    loading_embed = discord.Embed(
        title="Fetching Server Status...",
        description="Please wait a moment ⏳",
        color=discord.Color.greyple(),
    )
    await interaction.response.send_message(embed=loading_embed)

    # get message
    msg = await interaction.original_response()

    data = await get_server_status()
    if not data:
        await msg.edit(content="🛑 Could not reach server API.", embed=None, view=None)
        return
    embed = build_embed(data)

    await msg.edit(embed=embed, view=ControlView(data))

    last_status_data = data

    status_message = msg


# PC command group
pc_group = app_commands.Group(name="pc", description="PC server controls")


@pc_group.command(name="start", description="Start the PC server")
async def pc_start(interaction: discord.Interaction):
    await interaction.response.defer()
    status, data = await start_pc()
    if status == 200:
        await interaction.followup.send("🟢 PC starting...")
        await asyncio.sleep(5)
        await refresh_status()
    else:
        await interaction.followup.send(f"❌ Failed: {data}")


@pc_group.command(name="shutdown", description="Shut down the PC server")
async def pc_shutdown(interaction: discord.Interaction):
    await interaction.response.defer()
    status, data = await shutdown_pc()
    if status == 200:
        await interaction.followup.send("🔴 PC shutting down...")
        await asyncio.sleep(5)
        await refresh_status()
    else:
        await interaction.followup.send(f"❌ Failed: {data}")


@pc_group.command(name="restart", description="Restart the PC server")
async def pc_restart(interaction: discord.Interaction):
    await interaction.response.defer()
    status, data = await restart_pc()
    if status == 200:
        await interaction.followup.send("🔄 PC restarting...")
        await asyncio.sleep(10)
        await refresh_status()
    else:
        await interaction.followup.send(f"❌ Failed: {data}")


# Minecraft command group
mc_group = app_commands.Group(name="mc", description="Minecraft server controls")


@mc_group.command(name="start", description="Start the Minecraft server")
async def mc_start(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    status, data = await start_minecraft(name)
    if status == 200:
        await interaction.followup.send(f"🟢 {name} server starting...")
        await asyncio.sleep(5)
        await refresh_status()
    else:
        await interaction.followup.send(f"❌ Failed: {data}")


@mc_group.command(name="stop", description="Stop the Minecraft server")
async def mc_stop(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    status, data = await stop_minecraft(name)
    if status == 200:
        await interaction.followup.send(f"🔴 {name} stopped successfully")
        await asyncio.sleep(5)
        await refresh_status()
    else:
        await interaction.followup.send(f"❌ Failed: {data}")


@mc_group.command(name="restart", description="Restart the Minecraft server")
async def mc_restart(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    status, data = await restart_minecraft(name)
    if status == 200:
        await interaction.followup.send(f"🔄 {name} restarted successfully")
        await asyncio.sleep(10)
        await refresh_status()
    else:
        await interaction.followup.send(f"❌ Failed: {data}")


# Register both groups
client.tree.add_command(pc_group, guild=GUILD_ID)
client.tree.add_command(mc_group, guild=GUILD_ID)


@tasks.loop(seconds=30)  # every 30s, adjust as needed
async def update_status():
    global status_message
    if status_message:
        try:
            await refresh_status(message=status_message)
        except discord.NotFound:
            status_message = None


client.run(DISCORD_TOKEN)
