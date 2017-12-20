
import discord
import asyncio
import aiohttp
import json

"""
()
()	Handles requests from bot for data to post. 
()
"""
class Bot:
	def __init__(self, client: discord.Client, config: dict):
		self._client = client
		self._update_channel = config["update_channel"]

		# Data for updating
		self._mooning = config["mooning"]
		self._free_fall = config["free_fall"]
		self._over_bought = config["over_bought"]
		self._over_sold = config["over_sold"]
		self._interval = config["update_interval"]

		self._markets = {}
		self._updating = False
		
		# load markets asynchronously fun
		loop = asyncio.get_event_loop()
		task = loop.create_task(self._load_markets())
		future = asyncio.ensure_future(task)
		loop.run_until_complete(future)


	"""
	()
	()	Calculates and returns change in value between new_price and old_price
	()
	"""
	def _percent_change(self, new_price: int, old_price: int) -> float:
		return round( ( new_price - old_price ) / old_price, 2)


	"""
	()
	() Creates discord friendly formatting and returns it.
	()
	"""
	def _get_output(self, *args: list) -> str:
		ret = " ".join(args)
		ret.insert(0, "```\n")
		ret.append("```")

		return ret


	"""
	()
	()	** Make Asynchronous
	()
	()	Asynchronously loads the markets from bittrex and binance markets.
	()	This loaded data is used to check percent change.
	()
	"""
	async def _load_markets(self) -> None:
		async with aiohttp.ClientSession() as session:
			self._markets["Binance"] = json.loads( await self._get_binance_markets(session) )
			self._markets["Bittrex"] = json.loads( await self._get_bittrex_markets(session) )

	"""
	()
	()	Asynchronously gets market info from binance.
	()
	"""
	async def _get_binance_markets(self, session: aiohttp.ClientSession) -> str:
		async with session.get("https://api.binance.com/api/v1/ticker/allPrices") as resp:
			return await resp.text()


	"""
	()
	()	Asynchronously gets market info from bittrex.
	()
	"""
	async def _get_bittrex_markets(self, session: aiohttp.ClientSession) -> str:
		async with session.get("https://bittrex.com/api/v1.1/public/getmarketsummaries") as resp:
			return await resp.text()


	"""
	()
	()	Asynchronously receives market history from bittrex
	()
	"""
	async def _get_market_history(self, session:aiohttp.ClientSession, market: str) -> str:
		async with session.get("https://bittrex.com/api/v1.1/public/getmarkethistory?market={0}".format(market)) as resp:
			return await resp.text()

	"""
	()
	()	Processes market_history from bittrex
	()
	()	Returns a tuple of losses and gains: (loss, gain)
	()
	"""
	def _process_market_history(self, m_hist: dict) -> tuple: 

		loss = []
		gain = []

		result = m_hist["result"]

		last_price = None
		for buy in result.reverse():
			price = buy["Price"]
			if last_price:
				change = self._percent_change(price, last_price)

				if change < 0:
					loss.append(change)
					gain.append(0)

				else:
					gain.append(change)
					loss.append(0)

			last_price = price

		return (loss, gain)


	"""
	()
	()	Processes market_info from any market following protocol
	() 
	()	market_info = {
	()		"exchange": str,
	()		"market_name": str,
	()		"old_price": double,
	() 		"new_price": double,
	()		"1h": double,
	()		"24h": double,
	()	}
	()
	"""
	def _process_market(self, market_info: dict) -> str:
		exchange = market_info["exchange"]
		name = market_info["market_name"]
		old_price = market_info["old_price"]
		new_price = market_info["new_price"]

		change = self._percent_change(old_price, new_price)

		# possibility of RSI increase and price increase being triggered at the same time
		outs = []

		# Calculating RSI only works for bittrex rn
		if exchange == "Bittrex":
			rsi = self._calc_rsi(name)
			if rsi >= self._over_bought or rsi <= self._over_sold:
				outs.append( self._get_output ( [ name, "RSI:", str ( rsi ) ] ) )


		if change >= self._mooning or change <= self._free_fall:
			outs.append( self._get_output ( [ name, "changed by", str ( change ), "on", exchange ] ) )

		return outs


	"""
	()
	()	Calculates RSI and returns
	()
	()	RSI = 100 - ( 100 / ( 1 + RS ) )
	()
	()	RS = Average Gains / Average Losses
	()
	()	Average Gains: 
	()		1st avg gain = sum of gains over past n periods / n
	()		Everything after = (Prev Avg Gain * n-1 + current gain) / n
	()
	()	Average Loss:
	()		1st avg loss = sum of losses over past n period / n
	()		Everything after = (Prev Avg Gain * n-1 + current loss) / n
	()
	"""
	async def _calc_rsi(self, market: str) -> int:

		loss, gain = self._process_market_history( json.loads( await self._get_market_history ( market ) ) )
		
		history = market["prices"][-length::1]

		n = len(gain)

		average_gain = sum(gain) / n

		average_loss = sum(loss) / n
		
		try:
			RS = average_gain / average_loss
			RSI = int ( 100 - ( 100 / ( 1 + RS ) ) )

		except ZeroDivisionError:
			# No losses at all bb
			RSI = 100
		
		return RSI


	"""
	()
	()	checks binance markets for price updates, 
	()	if more than mooning/free_fall then flags it and creates output
	()
	()	Returns tuple of outputs & price updates
	()
	"""
	async def _check_binance_markets(self, session: aiohttp.ClientSession) -> tuple:
		outputs = []
		price_updates = {}

		new_markets = json.loads( await self._get_binance_markets(session) )

		old_markets = self._markets["Binance"]

		for i, old_market in enumerate(old_markets):

			new_market = new_markets[i]

			symb1 = old_market["symbol"]
			symb2 = new_market["symbol"]

			if symb1 == symb2:
				try:
					old_price = float(old_market["price"])
					new_price = float(new_market["price"])
				except:
					continue

				info = {
					"exchange": "Binance",
					"market_name": symb1,
					"old_price": old_price,
					"new_price": new_price,
				}

				out = self._process_market ( info )
				if out:
					outputs.extend(out)
					price_updates[i] = new_price

		return (outputs, price_updates)


	"""
	()
	()	checks bittrex markets for price updates, 
	()	if more than mooning/free_fall then flags it and creates output
	()
	()	Returns tuple of outputs & price updates
	()
	"""
	async def _check_bittrex_markets(self, session: aiohttp.ClientSession) -> tuple:
		outputs = []
		price_updates = {}

		new_markets = json.loads( await self._get_bittrex_markets(session) )

		old_markets = self._markets["Bittrex"]

		# get percent change through all the marketspyt
		for i, old_market in enumerate(old_markets["result"]):
			try:
				new_market = new_markets["result"][i]

				old_market_name = old_market["MarketName"]
				new_market_name = new_market["MarketName"]
			except IndexError: #idk
				continue 

			if old_market_name == new_market_name:
				try: 
					old_price = float(old_market["Last"])
					new_price = float(new_market["Last"])
				except:
					continue

				info = {
					"exchange": "Bittrex",
					"market_name": old_market_name,
					"old_price": old_price,
					"new_price": new_price,
					"1h": None,
					"24h": None,
				}

				out = self._process_market ( info ) 
				if out:
					outputs.extend(out)
					price_updates[i] = new_price

		return (outputs, price_updates)


	"""
	()
	()	Updates prices in markets dictionary !
	()
	"""
	def _update_prices(self, price_updates: dict) -> None:
		bittrex_markets = self._markets["Bittrex"]
		for i, price in price_updates["Bittrex"]:
			bittrex_markets[i]["Last"] = price

		binance_markets = self._markets["Binance"]
		for i, price in price_updates["Binance"]:
			binance_markets[i]["price"] = price


	"""
	()
	()	Checks both bittrex and binance markets, updates prices and sends outputs to websocket.
	()	Does while self._updating is true every interval minutes. Always does at least once.
	()
	"""
	async def check_markets(self, message: discord.Message) -> None:

		await self._client.send_message( message.channel , "@{0} Starting !".format(message.author) )

		async with aiohttp.ClientSession() as session:

			# loop through at least once
			while True:
				price_updates = {}

				outputs, price_updates["Bittrex"] = await self._check_bittrex_markets(session)
				outputs2, price_updates["Binance"] = await self._check_binance_markets(session)

				outputs.extend(outputs2)

				self._update_prices(price_updates)

				# upload to websocket
				print("Outputs:", outputs)
				for out in outputs:
					await self._client.send_message(self._update_channel, out)

				# if not continously updating break
				if not self._updating: 
					break

				await asyncio.sleep ( int ( interval * 60 ) )


	"""
	()
	()	Starts checking markets !
	()
	"""
	async def start_checking_markets(self, message: discord.Message) -> None:
		self._updating = True
		await self.check_markets(message)

	"""
	()
	()	Stops checking markets !
	()
	"""
	def stop_checking_markets(self) -> None:
		self._updating = False

	"""
	()
	()	Greets the person who said $greet
	()
	"""
	async def greet(self, message: discord.Message) -> None:
		await self._client.send_message(message.channel, "Hello @{0} !".format(message.author))


