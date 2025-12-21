import discord
from discord import app_commands
import asyncio
import json
import requests
import websocket
import threading
import time
from datetime import datetime
from datetime import datetime, timedelta


TOKEN = ("YOUR_DISCORD_BOT_TOKEN_HERE")
PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")

# Dm 

def safe_dm(loop, dm, message: str):
    asyncio.run_coroutine_threadsafe(dm.send(message), loop)

# start command

@tree.command(name="start", description="Start pump.fun watcher")
async def start_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("📩 Check your DMs.", ephemeral=True)

    user = interaction.user
    dm = await user.create_dm()

    await dm.send("🔐 Enter HELIUS API key:")

    def check(m):
        return m.author == user and m.channel == dm

    try:
        msg = await client.wait_for("message", timeout=300, check=check)
    except asyncio.TimeoutError:
        await dm.send("❌ Timed out.")
        return

    HELIUS_API_KEY = msg.content.strip()
    await dm.send("✅ API key received. Watching pump.fun...")
    print("User's Helius API Key:", HELIUS_API_KEY)

    loop = client.loop

    # Main sniping logic

    def on_open(ws):
        request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "logsSubscribe",
        "params": [
            {
                "mentions": [PROGRAM_ID]
            },
            {
                "commitment": "finalized"
            }
        ]
        }

        ws.send(json.dumps(request))


    def on_message(ws, message):
        data = json.loads(message)
        value = data.get("params", {}).get("result", {}).get("value", {})
        logs = value.get("logs", [])
        signature = value.get("signature")

        if logs or signature:
         print("<Finding token>")

         for log in logs:
              if "Instruction: CreatePool" in log:
                print("New pool detected:", signature)
                safe_dm(loop, dm, "🆕 New liquidity pool detected")
                getmint(signature)

    def on_error(ws, error):
        print("WebSocket error:", error)

    def on_close(ws, *_):
        print("WebSocket closed")

    def start_ws():
     while True:
        try:
            print("🔌 Connecting to Helius WS...")

            ws = websocket.WebSocketApp(
                f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}",
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            ws.run_forever(
                ping_interval=20,
                ping_timeout=10
            )

        except Exception as e:
            print("WS crashed:", e)
        print("🔁 Reconnecting .....")
        time.sleep(1)

    # Get token mint from transaction

    def getmint(signature: str):
        url = f"https://api-mainnet.helius-rpc.com/v0/transactions/?api-key={HELIUS_API_KEY}"
        res = requests.post(url, json={"transactions": [signature]})
        res.raise_for_status()

        parsed = res.json()

        for tx in parsed:
            for t in tx.get("tokenTransfers", []):
                mint = t.get("mint")
                if mint and "pump" in mint:
                    print("Pump mint:", mint)
                    safe_dm(loop, dm, f"🎯 Pump mint found:\n`{mint}`")
                    checktoken(mint)
                    return

    # Check token with Jupiter API

    def checktoken(mint: str):
        url = f"https://api.jup.ag/ultra/v1/search?query={mint}"
        headers = {"x-api-key": "YOUR_JUPITER_API_KEY_HERE"}

        r = requests.get(url, headers=headers)
        r.raise_for_status()

        data = r.json()
        if not data:
            return
       
        token = data[0]
        mcap = token.get("mcap", 0)
        holders = token.get("holderCount", 0)
        stats = token.get("stats5m", {})
        icon = token.get("icon", 0)
        thai_time = datetime.utcnow() + timedelta(hours=7)

        # dm results 

        if mcap >= 10_000 and holders >= 100 and stats.get("numBuys", 0) >= stats.get("numSells", 0):
          
          embed = discord.Embed(title="Token Analysis", color=0x00ff00)
          embed.add_field(name="Name", value=token.get("name"), inline=False)
          embed.add_field(name="MCAP", value=str(mcap), inline=False)
          embed.add_field(name="Holders", value=str(holders), inline=False)
          embed.add_field(name="Link", value=f"https://gmgn.ai/sol/token/{mint}", inline=False)
          embed.set_thumbnail(url=icon)
          embed.set_footer(text=f"Found at ⏱ {thai_time.strftime('%H:%M:%S')}")
          asyncio.run_coroutine_threadsafe(dm.send(embed=embed), loop)
          on_close(ws=None)
        
        else:
            safe_dm(loop, dm, "❌ Token did not pass filters")
            print("Waiting for next token...")

    threading.Thread(target=start_ws, daemon=True).start()

client.run(TOKEN)