
import logging
import asyncio
import json
import sys

import discord
import aiohttp


CONFIG_FILE = "config.json"


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
		self._rsi_tick_interval = config["rsi_tick_interval"]
		self._rsi_time_frame = config["rsi_time_frame"]
		
		# set up logging
		self._setup_logging(config)

		# Data for processing markets
		self._markets = {}
		self._significant_markets = set() # used for rsi to prevent spam printing
		self._updating = False
		
		# load markets asynchronously fun
		loop = asyncio.get_event_loop()
		task = loop.create_task(self._load_markets())
		future = asyncio.ensure_future(task)
		loop.run_until_complete(future)


	"""
	()
	()	Setups logging files/level
	()
	"""
	def _setup_logging(self, config: dict) -> None:
		self._logger = logging.getLogger(__name__)
		level = logging.INFO if config["debug"] == 0 else logging.DEBUG
		
		handler = logging.FileHandler("log.log")
		formatter = logging.Formatter(
			"%(asctime)s - %(name)s - %(levelname)% - %(message)s"
			)

		handler.setFormatter(formatter)
		handler.setLevel(level)

		self._logger.addHandler(handler)


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
		ret = "```\n"
		ret += " ".join(*args)
		ret += ("\n```")

		return ret


	"""
	()
	()	Asynchronously loads the markets from bittrex and binance markets.
	()	This loaded data is used to check percent change.
	()
	"""
	async def _load_markets(self) -> None:
		async with aiohttp.ClientSession() as session:
			self._markets["Binance"] = await self._get_binance_markets(session)
			self._markets["Bittrex"] = await self._get_bittrex_markets(session)


	"""
	()
	()	Asynchronously gets market info from binance.
	()
	"""
	async def _get_binance_markets(self, session: aiohttp.ClientSession) -> str:
		async with session.get("https://api.binance.com/api/v1/ticker/allPrices") as resp:
			try:
				return await resp.json()
			except aiohttp.errors.ServerDisconnectedError:
				self._logger.warning("binancemarket summaries ServerDisconnectedError")
				return {}


	"""
	()
	()	Asynchronously gets market info from bittrex.
	()
	"""
	async def _get_bittrex_markets(self, session: aiohttp.ClientSession) -> str:
		async with session.get("https://bittrex.com/api/v1.1/public/getmarketsummaries") as resp:
			try:
				return await resp.json()
			except aiohttp.errors.ServerDisconnectedError:
				self._logger.warning("bittrex market summaries ServerDisconnectedError")
				return {}


	"""
	()
	()	Asynchronously receives market history from bittrex
	()
	"""
	async def _get_market_history(self, session:aiohttp.ClientSession, market: str, tick_interval: str) -> str:
		async with session.get("https://bittrex.com/Api/v2.0/pub/market/GetTicks?marketName={0}&tickInterval={1}".format(market, tick_interval)) as resp:
			try:
				return await resp.json()
			except aiohttp.errors.ServerDisconnectedError:
				self._logger.warning("bittrex market history ServerDisconnectedError")
				return {}


	"""
	()
	()	Asynchronously processes market_info from any market following protocol
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
	async def _process_market(self, session:aiohttp.ClientSession, market_info: dict) -> str:
		exchange = market_info["exchange"]
		name = market_info["market_name"]
		old_price = market_info["old_price"]
		new_price = market_info["new_price"]

		change = self._percent_change(old_price, new_price)

		# possibility of RSI increase and price increase being triggered at the same time
		outs = []

		# Calculating RSI only works for bittrex rn
		if exchange == "Bittrex":
			rsi = await self._calc_rsi(session, name)

			if rsi >= self._over_bought or rsi <= self._over_sold:

				# make sure that rsi hasn't been significant yet
				if name not in self._significant_markets:
					outs.append( 
						self._get_output ( 
							[name, "RSI:", str(rsi)] 
							)
						)
					self._significant_markets.add(name)

			elif name in self._significant_markets:
				self._significant_markets.remove(name)



		if change >= self._mooning or change <= self._free_fall:
			outs.append( 
				self._get_output ( 
					[ name, "changed by", str ( change ), "on", exchange ] 
					) 
				)

		return outs


	"""
	()
	()	Processes market_history from bittrex and sorts them between
	()	losses and gains
	()
	()	Returns a tuple of losses and gains: (loss, gain)
	()
	"""
	def _process_market_history(self, m_hist: dict) -> tuple: 

		loss = []
		gain = []
		
		if not m_hist["result"]:
			return (loss, gain)

		result = m_hist["result"]

		last_price = None

		for buy in reversed(result):
			price = buy["O"] # gets opening price
			if last_price:
				change = self._percent_change(price, last_price)

				if change < 0:
					loss.append(abs(change))
					gain.append(0)

				else:
					gain.append(change)
					loss.append(0)

			last_price = price

		return (loss, gain)


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
	async def _calc_rsi(self, session: aiohttp.ClientSession, market: str) -> int:
		history = await self._get_market_history(
			session, market, self._rsi_tick_interval
			)

		loss, gain = self._process_market_history(history)

		n = len(gain)
		if n == 0:
			return 0

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

		new_markets = await self._get_binance_markets(session)

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

				out = await self._process_market ( session, info )
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

		new_markets = await self._get_bittrex_markets(session)

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

				out = await self._process_market ( session, info ) 
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
		bittrex_markets = self._markets["Bittrex"]["result"]
		for i, price in price_updates["Bittrex"].items():
			bittrex_markets[i]["Last"] = price

		binance_markets = self._markets["Binance"]
		for i, price in price_updates["Binance"].items():
			binance_markets[i]["price"] = price


	"""
	()
	()	Processes bittrex and binance markets, and sends outputs to discord.	
	()
	()	Does while self._updating is true every interval minutes. 
	()	Always does at least once.
	()
	"""
	async def check_markets(self) -> None:
		async with aiohttp.ClientSession() as session:

			# loop through at least once
			while True:
				price_updates = {}

				outputs, price_updates["Bittrex"] = await self._check_bittrex_markets(session)
				outputs2, price_updates["Binance"] = await self._check_binance_markets(session)

				outputs.extend(outputs2)

				self._update_prices(price_updates)

				for out in outputs:
					await self._client.send_message(discord.Object(id=self._update_channel), out)

				# if not continously updating break
				if not self._updating: 
					break

				await asyncio.sleep ( int ( self._interval * 60 ) )


	"""
	()
	()	Starts checking markets !
	()
	"""
	async def start_checking_markets(self, message: discord.Message) -> None:
		await self._client.send_message(
			message.channel , "Starting {0.author.mention} !".format(message)
			)
		await self.check_markets()


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
		await self._client.send_message(
			message.channel, "Hello {0.author.mention} !".format(message)
			)


if __name__ == '__main__':
	client = discord.Client()
	b = None;

	config = {}
	with open(CONFIG_FILE) as f:
		config = json.load(f)

	bot = Bot(client=client, config=config)


	@client.event
	async def on_ready():
		print("Logged in")


	@client.event
	async def on_message(message):
		content = message.content

		# Default greet
		if content.startswith("$greet"):
			await bot.greet(message)

		elif content.startswith("$help"):
			await client.send_message(
				message.channel, "```Starts checking bittrex and binance markets and prints the significant changes.\n" +
					"Args\n" + 
					"-h\tPrints this\n" + 
					"-i\tPeriod of time spent inbetween checking the markets\n" + 
					"-h\tHigh point to print notification\n" + 
					"-l\tLow point to print notification"
					)

		elif content.startswith("$start"):
			await bot.start_checking_markets(message)

		elif content.startswith("$stop"):
			bot.stop_checking_markets()

		elif content.startswith("$exit"):
			sys.exit()

	token = config["token"]
	client.run(token)
