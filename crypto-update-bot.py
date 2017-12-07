
import requests
import json
import time
import discord
import asyncio

CLIENT_TOKEN = "YOUR_ID_HERE"
CHANNEL_ID = "CHANNEL_ID_HERE"

MOONING = 4
FREE_FALL = -10

def get_percent_change(old_price, new_price):
	return round( float ( ( (new_price - old_price ) / old_price ) * 100 ), 2)


def get_output(market, percent_change, exchange):
	prefix = "increased by"
	if(percent_change < 0):
		prefix = "decreased by"

	everything = ["```\n", market, prefix, str(percent_change) + "%", "on " + exchange, "\n```"]
	return " ".join(everything)


def check_bittrex_markets(old_markets):

	outputs = []
	price_updates = {}

	while True:

		new_markets = json.loads(requests.get("https://bittrex.com/api/v1.1/public/getmarketsummaries").text)

		# get percent change through all the markets
		for i, market in enumerate(old_markets["result"]):

			old_market = market["MarketName"]
			new_market = new_markets["result"][i]["MarketName"]

			if old_market == new_market:
				try: 
					old_price = float(market["Last"])
					new_price = float(new_markets['result'][i]["Last"])
				except:
					continue

				percent_change = get_percent_change(old_price, new_price)
				
				if percent_change > MOONING || percent_change < FREE_FALL:
					output = get_output(new_market, percent_change, "Bittrex")

					outuputs.append(output)
					price_updates[i] = new_price	
					
				else:
					pass

	return (outputs, price_updates)


def check_binance_markets(old_markets):

	outputs = []
	price_updates = {}

	new_markets = json.loads(requests.get("https://api.binance.com/api/v1/ticker/allPrices").text)
		for i, old_market in enumerate(old_markets):

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
	 			
				if percent_change > MOONING || percent_change < FREE_FALL:
					output = get_output(symb2, percent_change, "Binance")
					outputs.append(output)

					price_updates[i] = new_price	

				else:
					pass

	return (outputs, price_updates)

@client.event
async def on_ready():
	
	mooning_wow = 4

	client = discord.Client()
	channel_id = "384895816998977543"
	target_channel = client.get_channel(channel_id)

	print("Logged in? ?? ")

	# await client.send_message(target_channel, 'Now Online')

	bittrex_markets = json.loads(requests.get("https://bittrex.com/api/v1.1/public/getmarketsummaries").text)
	binance_markets = json.loads(requests.get("https://api.binance.com/api/v1/ticker/allPrices").text)

	while True:

		# update bittrex markets
		outputs, price_updates = check_bittrex_markets(client, target_channel, bittrex_markets)
		for i, price in price_updates.items():
			bittrex_marketsn["result"][i]["Last"] = price

		
		# update Binance markets
		outputs2, price_updates = check_binance_markets(client, target_channel, binance_markets)
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
