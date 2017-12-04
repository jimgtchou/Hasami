import requests
import json
import time
import discord
import asyncio


CLIENT_TOKEN = "YOUR_ID_HERE"
CHANNEL_ID = "CHANNEL_ID_HERE"
client = discord.Client()

@client.event

async def on_ready():
	
	mooning_wow = 4
	target_channel = client.get_channel(CHANNEL_ID)

	print("Logged in? ?? ")

	# await client.send_message(target_channel, 'Now Online')

	bittrex_markets = json.loads(requests.get("https://bittrex.com/api/v1.1/public/getmarketsummaries").text)
	binance_prices = json.loads(requests.get("https://api.binance.com/api/v1/ticker/allPrices").text)

	while True:

		bittrex_markets2 = json.loads(requests.get("https://bittrex.com/api/v1.1/public/getmarketsummaries").text)

		# get percent change through all the markets
		for i, market in enumerate(bittrex_markets["result"]):

			old_market = market["MarketName"]
			new_market = bittrex_markets2["result"][i]["MarketName"]

			if old_market == new_market:
				try: 
					old_price = float(market["Last"])
					new_price = float(bittrex_markets2['result'][i]["Last"])
				except:
					continue

				# print(old_price, new_price)

				percent_change = round( float( ( ( new_price - old_price ) / old_price ) * 100 ) , 2)
				
				if percent_change > mooning_wow:

					# market_format = "(" + new_market + ")"
					# percent_format = "[" + str(percent_change) + "]"

					everything = ["```asciidoc\n", new_market, " increased by ", str(percent_change), " on Bittrex ", "\n```"]
					output = " ".join(everything)
					
					bittrex_markets['result'][i]["Last"] = new_market #?

					await client.send_message(target_channel, output) 
					await asyncio.sleep(1)
					

				else:
					pass

		binance_prices2 = json.loads(requests.get("https://api.binance.com/api/v1/ticker/allPrices").text)
		for i, old_market in enumerate(binance_prices):

			new_market = binance_prices2[i]

			symb1 = old_market["symbol"]
			symb2 = new_market["symbol"]

			if symb1 == symb2:
				try:
					old_price = float(old_market["price"])
					new_price = float(new_market["price"])
				except:
					continue

				percent_change = round( float( ( ( new_price - old_price ) / old_price) * 100) , 2 )
	 			
				if percent_change > mooning_wow:

					# symb1_format = "(" + symb1 + ")"
					# percent_format = "[" + str(percent_change) + "]"

					everything = ["```asciidoc\n", symb1, " increased by ", str(percent_change), " on Binance", "\n```"]
					output = "".join(everything)

					binance_prices[i]["price"] = new_price

					await client.send_message(target_channel, output)
					await asyncio.sleep(1)

				else:
					pass

		#time.sleep(20)
		await asyncio.sleep(40)
		   

client.run(CLIENT_TOKEN)
