#!/usr/bin/env python3
import discord
from discord.ext import commands, tasks
from discord import ui
import asyncio
import os
import datetime
import json
from dotenv import load_dotenv

# Import your existing local agent logic
import buddy_agent

# Load environment variables
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(CURRENT_DIR, ".env"))

# Configuration
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('DISCORD_GUILD_ID')

# Channel Mapping
CHANNELS = {
    'general': int(os.getenv('CHANNEL_GENERAL', 0)),
    'engineer': int(os.getenv('CHANNEL_ENGINEER', 0)),
    'monitoring': int(os.getenv('CHANNEL_MONITORING', 0)),
    'vision': int(os.getenv('CHANNEL_VISION', 0)),
    'librarian': int(os.getenv('CHANNEL_LIBRARIAN', 0)),
    'planner': int(os.getenv('CHANNEL_PLANNER', 0)),
    'shopping': int(os.getenv('CHANNEL_SHOPPING', 0))
}

PENDING_PATH = os.path.join(CURRENT_DIR, "modules/approvals/pending.json")

class PlanningView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Show Tasks", style=discord.ButtonStyle.primary)
    async def show_tasks(self, interaction: discord.Interaction, button: ui.Button):
        import task_manager
        tasks = task_manager.list_tasks()
        await interaction.response.send_message(f"```\n{tasks}\n```", ephemeral=True)

    @ui.button(label="Show Notes", style=discord.ButtonStyle.secondary)
    async def show_notes(self, interaction: discord.Interaction, button: ui.Button):
        from modules.toolbox import Toolbox
        notes = Toolbox.list_notes()
        await interaction.response.send_message(f"```\n{notes}\n```", ephemeral=True)

    @ui.button(label="Refine Forge", style=discord.ButtonStyle.blurple)
    async def refine_forge(self, interaction: discord.Interaction, button: ui.Button):
        from modules.toolbox import Toolbox
        await interaction.response.send_message("🛠️ **Waking Architect (30B)... Refinement Started.**", ephemeral=True)
        # Run in background to avoid blocking
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, Toolbox.refine_forge)
        await interaction.followup.send(f"✅ **Refinement Complete:** {res}")

    @ui.button(label="Refresh Dashboard", style=discord.ButtonStyle.green)
    async def refresh_dash(self, interaction: discord.Interaction, button: ui.Button):
        from modules.dashboard import get_dashboard
        dash = get_dashboard()
        await interaction.response.edit_message(content=f"```\n{dash}\n```", view=self)

class ApprovalView(ui.View):
    def __init__(self, approval_id, bot):
        super().__init__(timeout=None)
        self.approval_id = approval_id
        self.bot = bot

    @ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        await self.update_status("approved", interaction)

    @ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: ui.Button):
        await self.update_status("denied", interaction)

    async def update_status(self, status, interaction):
        try:
            if not os.path.exists(PENDING_PATH): return
            
            with open(PENDING_PATH, 'r+') as f:
                queue = json.load(f)
                if self.approval_id in queue:
                    queue[self.approval_id]['status'] = status
                    f.seek(0)
                    json.dump(queue, f, indent=4)
                    f.truncate()
                    await interaction.response.send_message(f"✅ Action {status}.", ephemeral=True)
                    self.stop()
                    # Update the message to reflect the decision
                    await interaction.message.edit(content=f"**Status: {status.upper()}**", view=None)
                else:
                    await interaction.response.send_message("❌ Error: Request not found or already processed.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating status: {e}", ephemeral=True)

class ShopBuddyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.bot_loop = None
        
    async def setup_hook(self):
        self.bot_loop = asyncio.get_running_loop()
        self.proactive_briefing.start()
        self.check_pending_approvals.start()
        self.update_planner_dashboard.start()
        self.check_new_refinements.start()

    @tasks.loop(seconds=60)
    async def check_new_refinements(self):
        from modules.forge import FORGE_REFINED_PATH
        if not os.path.exists(FORGE_REFINED_PATH): return
        
        try:
            refined_entries = []
            updated = False
            with open(FORGE_REFINED_PATH, 'r') as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if not entry.get('posted_to_discord'):
                            channel = self.get_channel(CHANNELS['monitoring'])
                            if channel:
                                embed = discord.Embed(title="✨ NEW ARCHITECT PROPOSAL", color=discord.Color.blue())
                                embed.add_field(name="Concept", value=entry['thought'], inline=False)
                                content = entry['refined_content']
                                if len(content) > 1024: content = content[:1021] + "..."
                                embed.add_field(name="Preview", value=f"```markdown\n{content}\n```", inline=False)
                                embed.set_footer(text=f"Refined at: {entry.get('refined_at', 'Unknown')}")
                                await channel.send(embed=embed)
                                entry['posted_to_discord'] = True
                                updated = True
                        refined_entries.append(entry)
            
            if updated:
                with open(FORGE_REFINED_PATH, 'w') as f:
                    for entry in refined_entries:
                        f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"Refinement Loop Error: {e}")

    @tasks.loop(seconds=30)
    async def update_planner_dashboard(self):
        channel = self.get_channel(CHANNELS['planner'])
        if not channel:
            try:
                channel = await self.fetch_channel(CHANNELS['planner'])
            except:
                return
        if not channel: return
        
        from modules.dashboard import get_dashboard
        dash = get_dashboard()
        
        # Look for existing dashboard message to edit, or post new
        dashboard_msg = None
        async for message in channel.history(limit=50):
            if message.author == self.user and "APOLLO SYSTEM DASHBOARD" in message.content:
                if not dashboard_msg:
                    dashboard_msg = message
                else:
                    try:
                        await message.delete() # Clean up duplicate spam
                    except: pass
        
        if dashboard_msg:
            await dashboard_msg.edit(content=f"```\n{dash}\n```", view=PlanningView(self))
        else:
            # If not found, post a fresh one
            await channel.send(f"```\n{dash}\n```", view=PlanningView(self))

    @tasks.loop(seconds=5)
    async def check_pending_approvals(self):
        if not os.path.exists(PENDING_PATH): return
        
        try:
            with open(PENDING_PATH, 'r+') as f:
                queue = json.load(f)
                updated = False
                for q_id, data in queue.items():
                    if data.get('status') == 'pending' and not data.get('posted'):
                        channel = self.get_channel(CHANNELS['monitoring'])
                        if not channel:
                            try:
                                channel = await self.fetch_channel(CHANNELS['monitoring'])
                            except:
                                print(f"Approval Loop Warning: Could not fetch channel {CHANNELS['monitoring']}")
                                continue
                                
                        if channel:
                            embed = discord.Embed(title="⚠️ SECURITY APPROVAL REQUIRED", color=discord.Color.gold())
                            embed.add_field(name="Action", value=data['action'], inline=False)
                            params_str = str(data['params'])
                            embed.add_field(name="Parameters", value=f"```json\n{params_str[:1000]}\n```", inline=False)
                            embed.set_footer(text=f"ID: {q_id}")
                            
                            view = ApprovalView(q_id, self)
                            await channel.send(content="@everyone ⚠️ **Security Approval Required**", embed=embed, view=view)
                            data['posted'] = True
                            updated = True
                
                if updated:
                    f.seek(0)
                    json.dump(queue, f, indent=4)
                    f.truncate()
        except Exception as e:
            print(f"Approval Loop Error: {e}")

    async def log_to_discord(self, message):
        """Helper to send debug logs to the #monitoring channel."""
        print(f"[LOG] {message}")
        channel = self.get_channel(CHANNELS['monitoring'])
        if channel:
            # Chunking for Discord limits
            clean_msg = message.replace("```", "'''") # Prevent nested backticks
            if len(clean_msg) > 1900:
                for i in range(0, len(clean_msg), 1900):
                    await channel.send(f"```\n{clean_msg[i:i+1900]}\n```")
            else:
                await channel.send(f"```\n{clean_msg}\n```")

    def log_sync(self, msg):
        """Thread-safe synchronous wrapper for log_to_discord."""
        if self.bot_loop:
            asyncio.run_coroutine_threadsafe(self.log_to_discord(msg), self.bot_loop)

    @tasks.loop(time=datetime.time(hour=7, minute=0))
    async def proactive_briefing(self):
        await self.log_to_discord("Autonomous Task: Starting Morning Briefing...")
        channel = self.get_channel(CHANNELS['monitoring'])
        if channel:
            loop = asyncio.get_running_loop()
            response, _ = await loop.run_in_executor(None, buddy_agent.chat_with_buddy, "Give me a daily system status and hardware brief.", self.log_sync)
            await channel.send(f"🌅 **Morning Briefing:**\n{response}")

    @commands.command()
    async def forge(self, ctx, *, thought: str):
        """Captures a raw engineering vision into the Forge."""
        from modules.toolbox import Toolbox
        res = Toolbox.forge_idea(thought)
        await ctx.send(f"⚒️ **Forged:** {res}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        # Log ALL incoming traffic in OS channels to monitoring for transparency
        if message.channel.id in CHANNELS.values():
            await self.log_to_discord(f"TRAFFIC: Channel #{message.channel.name} | User: {message.author} | Content: {message.content[:100]}...")

        # Process commands first (!forge, etc)
        ctx = await self.get_context(message)
        if ctx.valid:
            await self.process_commands(message)
            return # Stop here if it was a command

        if self.user.mentioned_in(message) or message.channel.id in CHANNELS.values():
            async with message.channel.typing():
                prompt_context = ""
                user_content = message.content.replace(f'<@{self.user.id}>', '').strip()

                if message.channel.id == CHANNELS['engineer']:
                    prompt_context = "[FORCE DEV_BUDDY] "
                elif message.channel.id == CHANNELS['monitoring']:
                    prompt_context = "[FORCE FAST_PATH] "
                elif message.channel.id == CHANNELS['vision']:
                    prompt_context = "[FORCE ARCHITECT] " if "[FORCE ARCHITECT]" in user_content else "[FORCE VISION] "
                    if message.attachments:
                        for attachment in message.attachments:
                            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                                os.makedirs('tmp/vision', exist_ok=True)
                                local_path = f"tmp/vision/{attachment.filename}"
                                await attachment.save(local_path)
                                prompt_context += f"[ATTACHED_IMAGE: {local_path}] "
                                await self.log_to_discord(f"DEBUG: Saved attachment to {local_path}")
                elif message.channel.id == CHANNELS['librarian']:
                    prompt_context = "[FORCE LIBRARIAN] "
                    if message.attachments:
                        for attachment in message.attachments:
                            if attachment.filename.lower().endswith('.pdf'):
                                os.makedirs('vault/cold', exist_ok=True)
                                local_path = os.path.join('vault/cold', attachment.filename)
                                await attachment.save(local_path)
                                prompt_context += f"[ATTACHED_PDF: {local_path}] "
                                await self.log_to_discord(f"DEBUG: Saved PDF to {local_path}")
                elif message.channel.id == CHANNELS['shopping']:
                    prompt_context = "[FORCE PROCUREMENT] "
                    if message.attachments:
                        for attachment in message.attachments:
                            # Handle both images and PDFs
                            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                                os.makedirs('tmp/vision', exist_ok=True)
                                local_path = os.path.join('tmp/vision', attachment.filename)
                                await attachment.save(local_path)
                                prompt_context += f"[ATTACHED_IMAGE: {local_path}] "
                            elif attachment.filename.lower().endswith('.pdf'):
                                os.makedirs('vault/cold', exist_ok=True)
                                local_path = os.path.join('vault/cold', attachment.filename)
                                await attachment.save(local_path)
                                prompt_context += f"[ATTACHED_PDF: {local_path}] "
                
                if not user_content and "[ATTACHED_IMAGE" in prompt_context:
                    user_content = "Describe this image in detail."
                if not user_content and "[ATTACHED_PDF" in prompt_context:
                    user_content = "Ingest and summarize this PDF."
                final_prompt = f"{prompt_context}{user_content}"
                
                loop = asyncio.get_running_loop()
                try:
                    # Pass self.log_sync to the local agent so it can broadcast status updates back to Discord
                    response, _ = await loop.run_in_executor(None, buddy_agent.chat_with_buddy, final_prompt, self.log_sync)
                    
                    if response:
                        if len(response) > 1900:
                            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                            for chunk in chunks:
                                await message.channel.send(chunk)
                        else:
                            await message.channel.send(response)
                except Exception as e:
                    await self.log_to_discord(f"CRITICAL ERROR: {str(e)}")
                    await message.channel.send(f"⚠️ **Core Fault:** {e}")

bot = ShopBuddyBot()

if __name__ == '__main__':
    bot.run(TOKEN)
