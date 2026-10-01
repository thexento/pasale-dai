import os
import uuid
import discord
from discord.ext import commands
from dotenv import load_dotenv
from app.ai.gemini import ask_gemini

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("pong")

@bot.command(name="ask")
async def ask(ctx, *, prompt: str):
    async with ctx.typing():
        response = await ask_gemini(prompt)
        if len(response) > 2000:
            for chunk in [response[i:i + 1900] for i in range(0, len(response), 1900)]:
                await ctx.send(chunk)
        else:
            await ctx.send(response)

@bot.command(name="pay")
async def pay(ctx, amount: float = 100.0):
    txn_id = str(uuid.uuid4())
    checkout_url = f"{BASE_URL}/checkout?amount={amount}&txn_id={txn_id}"
    
    embed = discord.Embed(title="eSewa Payment", color=0x60BB46)
    embed.add_field(name="Amount", value=f"NPR {amount}", inline=False)
    embed.add_field(name="Transaction ID", value=txn_id, inline=False)
    embed.add_field(name="Payment Link", value=f"[Pay with eSewa]({checkout_url})", inline=False)
    await ctx.send(embed=embed)