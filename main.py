
import discord
import asyncio
import shlex
import json
import bot
import sys

CONFIG_FILE = "config.json"

client = discord.Client()
bot = bot.Bot(client)

@client.event
async def on_ready():
	print("Logged in")


@client.event
async def on_message(message):
	content = message.content

	# Default greet
	if content.startswith("$greet"):
		await bot.greet(message)

	elif content.startswith("$start"):
		args = []
		if "-h" in args:
			await client.send_message(message.channel, "```Starts checking bittrex and binance markets and prints the significant changes.\n" +
				"Args\n" + 
				"-h\tPrints this\n" + 
				"-i\tPeriod of time spent inbetween checking the markets\n" + 
				"-h\tHigh point to print notification\n" + 
				"-l\tLow point to print notification")

		else:
			await bot.start_checking_markets(message)

	elif content.startswith("$check"):
		await bot.check_markets(message.channel)

	elif content.startswith("$rsi"):
		market = message.split(" ")[1]
		await bot.generate_rsi(market)

	elif content.startswith("$stop"):
		bot.stop_checking_markets()

	elif content.startswith("$exit"):
		sys.exit()

def main():
	config = {}
	with open(CONFIG_FILE) as f:
		config = json.load(f)

	token = config["token"]

	client = discord.Client()
	bot = bot.Bot(client, config=config)

	client.run(token)




if __name__ == '__main__':
	main()
