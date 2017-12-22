
import discord
import asyncio
import shlex
import json
import bot
import sys

CONFIG_FILE = "config.json"

client = discord.Client()
b = None;

config = {}
with open(CONFIG_FILE) as f:
	config = json.load(f)

token = config["token"]
b = bot.Bot(client=client, config=config)


@client.event
async def on_ready():
	print("Logged in")


@client.event
async def on_message(message):
	content = message.content

	# Default greet
	if content.startswith("$greet"):
		await b.greet(message)

	elif content.startswith("$help"):
		await client.send_message(message.channel, "```Starts checking bittrex and binance markets and prints the significant changes.\n" +
				"Args\n" + 
				"-h\tPrints this\n" + 
				"-i\tPeriod of time spent inbetween checking the markets\n" + 
				"-h\tHigh point to print notification\n" + 
				"-l\tLow point to print notification")

	elif content.startswith("$start"):
		await b.start_checking_markets(message)

	elif content.startswith("$stop"):
		b.stop_checking_markets()

	elif content.startswith("$exit"):
		sys.exit()


client.run(token)
