
import time
import discord
import asyncio
import websocket
from backend_shoe import *

client = discord.Client()

CLIENT_TOKEN = "YOUR_TOKEN_HERE"
CHANNEL_ID = "YOUR_CHANNEL_ID"
MOONING = 4
FREE_FALL = -10	

def get_percent_change(old_price, new_price):
	return round( float ( ( (new_price - old_price ) / old_price ) * 100 ) 	, 2)


def get_output(market, percent_change, exchange):
	prefix = "increased by"
	if(percent_change < 0):
		prefix = "decreased by"

	everything = ["```\n", market, prefix, str(percent_change) + "%", "on" + exchange, "\n```"]
	return " ".join(everything)

@client.event
async def on_ready():
	target_channel = client.get_channel(CHANNEL_ID)
	print("Logged in? ?? ")

	# await client.send_message(target_channel, 'Now Online')

	bittrex_markets = json.loads(requests.get("https://bittrex.com/api/v1.1/public/getmarketsummaries").text)
	binance_markets = json.loads(requests.get("https://api.binance.com/api/v1/ticker/allPrices").text)

	market_history = {}

	while True:

		# update bittrex markets
		outputs, price_updates = check_bittrex_markets(bittrex_markets)
		for i, price in price_updates.items():
			market = bittrex_markets["result"][i]
			
			# Calculate RSI
			change = get_percent_change(market["Last"], price)
			if(market not in market_history):
				market_history[market] = {"gains": [], "losses": []}
			else:
				if change > 0:
					market_history[market]["gains"]
					
			market["Last"] = price


		# update Binance markets
		outputs2, price_updates = check_binance_markets(binance_markets)
		for i, price in price_updates.items():
			binance_markets[i]["price"] = price

		# send out outputs
		outputs.extend(outputs2)
		for out in outputs:
			await client.send_message(target_channel, out)
			await asyncio.sleep(1)
					

		#time.sleep(20)
		await asyncio.sleep(40)

client.run(CLIENT_TOKEN)
