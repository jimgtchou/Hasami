
import logging.config
import logging
import asyncio
import yaml
import json
import sys

import discord
import aiohttp

import datetime


CONFIG_FILE = "config.json"
LOGGING_CONFIG = "log_conf.yaml"


class Bot:
	"""
	Bot used to analyze the Binance markets for significant price changes and
	RSI values.

	These significant markets are then printed out into a discord server.

	Attributes:
		client: Client used to communicate with the discord server
		config: configuration to edit the bot.
		logger: Logger to be used when logging.
		_mooning: High significant price change.
		_free_fall: Low significant price change.
		_over_bought: High significant RSI val.
		_over_sold: Low significant RSI val.
		_interval: Time to wait between each analysis of the markets.
		_rsi_tick_interval: Interval between each price update used to calculate the markets.
		_rsi_time_frame: Number of candles used to calculate RSI.


	"""
	def __init__(self, client: discord.Client, config: dict, logger: logging.Logger):
		self._client = client
		self._logger = logger

		# config stuff
		self._mooning = config["mooning"]
		self._free_fall = config["free_fall"]
		self._over_sold = config["over_sold"]
		self._over_bought = config["over_bought"]
		self._interval = config["update_interval"]
		self._update_channel = config["update_channel"]
		self._rsi_time_frame = config["rsi_time_frame"]
		self._rsi_tick_interval = config["rsi_tick_interval"]
		self._vol_threshold = config["vol_threshold"]

		# Data for processing markets
		self._markets = {}

		self._significant_markets = set() # used for rsi to prevent spam printing
		self._updating = False

		self._markets_volume = {}
		self._rsi_tick_interval_Binance_mapping = {
			'oneMin':'1m',
			'fiveMin':'5m',
			'fifteenMin':'15m',
			'thirtyMin':'30m',
			'day':'1d'
			}



	def _percent_change(self, new_price: int, old_price: int) -> float:
		"""
		Calculates and returns change in value between new_price and old_price

		Args:
			new_price: new price to be compared to old price.
			old_price: old price to be compared to new price.

		Returns:
			Float of the percent change rounded to 4 sig figs. IE 60.49

		"""
		return round((new_price - old_price) / old_price, 4) * 100


	def _get_output(self, *items: list) -> str:
		"""
		Creates a discord friendly formatting and returns it.

		Args:
			*items: Items to concatonate together into one output.

		Returns:
			Discord friendly text !

		"""
		ret = "```\n"
		ret += " ".join(*items)
		ret += ("\n```")

		return ret


	async def _query_exchange(self, session: aiohttp.ClientSession, url: str, depth: int = 0,
		max_depth: int = 3) -> dict:
		"""
		Tries to GET data from the exchange with url. If it fails it
		recursively retries max_depth number of times.

		Args:
			url: The url of the server to get data from.
			depth: The current try at getting data
			max_depth: The maximum number of retries the bot will do.

		Returns:
			A json dict from the server specified by url if sucessful, else empty dict.

		"""

		if depth == max_depth:
			self._logger.warning("{0} Failed to GET data. Depth: {1}".format(url, depth))
			return {}

		try:
			async with session.get(url) as resp:
				data = await resp.json()
				if 'code' in data:
					print(data['msg'])
					sys.exit()
				return data
		except aiohttp.errors.ServerDisconnectedError:
			self._logger.warning("{0} ServerDisconnectedError".format(url))
			return await self._query_exchange(session, url, depth=depth+1)


	async def _load_markets(self, session: aiohttp.ClientSession) -> None:
		"""
		Asynchronously loads the markets from  Binance markets.
		This loaded data is used to check percent change.

		Args:
			session: The aiohttp session to be used to query the markets

		Returns:
			None

		"""
		self._markets["Binance"] = {}
		temp_binance_markets = await self._get_binance_markets(session)
		temp_binance_markets_volume = await self._get_binance_markets_volume(session)

		for mvol in temp_binance_markets_volume:
			if mvol['symbol'].startswith('BTC') or mvol['symbol'].endswith('BTC'):
				self._markets_volume[mvol['symbol']] = round(float(mvol['quoteVolume']),2)

		for m in temp_binance_markets:
			if m['symbol'].startswith('BTC') or m['symbol'].endswith('BTC'):
				if self._markets_volume[m['symbol']] > self._vol_threshold:
					market = {'symbol':m['symbol'], 'price':m['price']}
					self._markets["Binance"][m['symbol']] = m


	async def _get_binance_markets(self, session: aiohttp.ClientSession) -> dict:
		"""
		Asynchronously GETS the market summaries from binance and returns
		it as a dictionary.

		Args:
			session: The aiohttp ClientSession to be used to GET data from exchange
			market summaries from binance.

		Returns:
			A dictionary of the market summaries from binance.

		"""
		url = "https://api.binance.com/api/v1/ticker/allPrices"
		return await self._query_exchange(session, url)

	async def _get_binance_markets_volume(self, session: aiohttp.ClientSession) -> dict:
		"""
		Asynchronously GETS the market summaries from binance and returns
		it as a dictionary.

		Args:
			session: The aiohttp ClientSession to be used to GET data from exchange
			market summaries from binance.

		Returns:
			A dictionary of the market summaries from binance.

		"""
		url = "https://api.binance.com/api/v1/ticker/24hr"
		return await self._query_exchange(session, url)


	async def _get_market_history(self, session:aiohttp.ClientSession, market: str,
		tick_interval: str, exchange: str) -> dict:
		"""
		Asynchronously receives market history from Binance and returns it as a dict.

		Args:
			session: The aiohttp ClientSession to be used to GET data from exchange
			market history from Binance.
			market: The market who's history it should receive.
			tick_interval: Tick interval used when querying Binance.

		Returns:
			Dict of the market history with tick interval of tick interval.

		"""

		if exchange == "Binance":
			url = "https://api.binance.com/api/v1/klines?symbol={0}&interval={1}&limit={2}".format(
				market, self._rsi_tick_interval_Binance_mapping[tick_interval], 500)

		return await self._query_exchange(session, url)


	def _process_market_history(self, m_hist: dict, exchange: str) -> tuple:
		"""

		Processes market_history from Binance and sorts them between
		losses and gains.

		Args:
			m_hist: The history of market to process.

		Returns:
			Tuple of losses and gains: (loss, gain)

		"""

		loss = []
		gain = []

		if exchange == "Binance":
			if not m_hist:
				return (loss, gain)

			result = m_hist

			last_price = None

		for buy in reversed(result):
			if exchange == "Binance":
				price = float(buy[1]) # gets current price
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


	async def _calc_rsi(self, session: aiohttp.ClientSession, market: str, exchange: str) -> int:
		"""
		Calculates & Returns the RSI of market according to the RSI formula

		RSI = 100 - ( 100 / ( 1 + RS ) )

		RS = Average Gains / Average Losses

		Average Gains
			1st avg gain = sum of gains over past n periods / n
			Everything after = (Prev Avg Gain * n-1 + current gain) / n

		Average Loss
			1st avg loss = sum of losses over past n period / n
			Everything after = (Prev Avg Gain * n-1 + current loss) / n

		Args:
			session: The aiohttp ClientSession to be used to GET data from exchanges.
			market: The market to calculate RSI for.

		Returns:
			The RSI of market.


		"""
		history = await self._get_market_history(
			session, market, self._rsi_tick_interval, exchange
			)

		loss, gain = self._process_market_history(history, exchange)

		n = len(gain)
		frame = self._rsi_time_frame
		if n == 0:
			return 0

		average_gain = sum(gain[0:frame]) / frame
		average_loss = sum(loss[0:frame]) / frame

		smooth = lambda x,y: (x*(frame-1)+y)/frame

		for g, l in list(zip(gain, loss))[frame:]:
			average_gain = smooth(average_gain,g)
			average_loss = smooth(average_loss,l)

		try:
			RS = average_gain / average_loss
			RSI = int ( 100 - ( 100 / ( 1 + RS ) ) )

		except ZeroDivisionError:
			# No losses at all bb
			RSI = 100

		return RSI


	async def _process_market(self, session: aiohttp.ClientSession, market_info: dict) -> list:
		"""
		Asynchronously processes market_info from any market following protocol.
		Generates outputs for significant RSIs/price changes.

		market_info = {
			"exchange": str,
			"market_name": str,
			"old_price": double,
	 		"new_price": double,
			"1h": double,
			"24h": double,
		}

		Args:
			session: The aiohttp ClientSession to be used to GET data from exchange
			market_info: Market info, follows format {
				"exchange": str,
				"market_name": str,
				"old_price": double,
		 		"new_price": double,
				"1h": double,
				"24h": double,
			}

		Returns:
			List of all outputs from signifcant price changes / RSIs

		"""
		exchange = market_info["exchange"]
		name = market_info["market_name"]
		old_price = market_info["old_price"]
		new_price = market_info["new_price"]

		# self._logger.debug("Processing {0}".format(name))

		change = self._percent_change(new_price, old_price)
		self._logger.debug("{0} Change {1} old_price {2} new_price {3}".format(name, change, old_price, new_price))

		# possibility of RSI increase and price increase being triggered at the same time
		outs = []

		# Calculating RSI for Binance
		rsi = await self._calc_rsi(session, name, exchange)
		self._logger.debug("RSI {0}".format(rsi))
		if rsi >= self._over_bought or rsi <= self._over_sold or change >= self._mooning or change <= self._free_fall:
			sig_rsi = ""
			sig_change = ""
			if rsi >= self._over_bought or rsi <= self._over_sold:
				sig_rsi = "*"
			if change >= self._mooning or change <= self._free_fall:
				sig_change = "*"
			# make sure that rsi hasn't been significant yet
			if name not in self._significant_markets:
				if self._markets_volume[name] > self._vol_threshold:
					self._logger.debug("Not significant yet, creating output")
					outs.append(
						self._get_output (
							["{}:".format(name), "{}RSI={}".format(sig_rsi,rsi), "{}Change={}".format(sig_change,round(change,2)) , "Vol={}".format(self._markets_volume[name])]
							)
						)
					self._significant_markets.add(name)

		elif name in self._significant_markets:
			self._logger.debug(
				"Previously significant, no longer significant, removing."
				)
			self._significant_markets.remove(name)

		self._logger.debug("Outputs: {0}".format(outs))
		return outs


	async def _check_binance_markets(self, session: aiohttp.ClientSession) -> tuple:
		"""
		Checks binance markets for significant price/rsi updates.

		Args:
			session: The aiohttp ClientSession to be used to GET data from binance

		Returns:
			tuple of outputs & price updates

		"""
		outputs = []
		now = datetime.datetime.now()
		outputs.append("```\n---Time {}---\n```".format(now.strftime("%Y-%m-%d %H:%M")))

		price_updates = {}
		new_markets = {}
		temp_binance_markets = await self._get_binance_markets(session)
		temp_binance_markets_volume = await self._get_binance_markets_volume(session)

		for mvol in temp_binance_markets_volume:
			if mvol['symbol'].startswith('BTC') or mvol['symbol'].endswith('BTC'):
				self._markets_volume[mvol['symbol']] = round(float(mvol['quoteVolume']),2)

		for m in temp_binance_markets:
			if m['symbol'].startswith('BTC') or m['symbol'].endswith('BTC'):
				if self._markets_volume[m['symbol']] > self._vol_threshold:
					new_markets[m['symbol']] = m


		old_markets = self._markets["Binance"]
		self._markets["Binance"] = new_markets

		self._significant_markets.clear()
		for k,new_market in new_markets.items():

			market_symbol = new_market["symbol"]

			if market_symbol in old_markets:
				old_market = old_markets[market_symbol]

				try:
					old_price = float(old_market["price"])
					new_price = float(new_market["price"])
				except:
					continue

				info = {
					"exchange": "Binance",
					"market_name": market_symbol,
					"old_price": old_price,
					"new_price": new_price,
				}

				out = await self._process_market(session, info)
				if out:
					outputs.extend(out)

			else:
				new_price = float(new_market["price"])
				info = {
					"exchange": "Binance",
					"market_name": market_symbol,
					"old_price": new_price,
					"new_price": new_price,
				}
				out = await self._process_market(session, info)
				if out:
					outputs.extend(out)


		return (outputs, price_updates)


	async def check_markets(self) -> None:
		"""
		Processes Binance markets for signifcant price/rsi updates
		and sends outputs to discord.

		Does while self._updating is true every interval minutes.

		Args:
			None

		Returns:
			None

		"""
		async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:

			# load markets
			await self._load_markets(session)

			# loop through at least once
			while self._updating:
				price_updates = {}

				self._logger.info("Checking markets")

				outputs, price_updates["Binance"] = await self._check_binance_markets(
					session
					)

				self._logger.debug("Outputs: {0}".format(outputs))

				for out in outputs:
					self._logger.info("Out: {0}".format(out))
					await self._client.send_message(
						discord.Object(id=self._update_channel),
						out
						)

				self._logger.debug("Async sleeping {0}".format(str(self._interval * 60)))
				await asyncio.sleep ( int ( self._interval * 60 ) )
				print("------new iteration------")


	async def start_checking_markets(self, message: discord.Message) -> None:
		"""
		Begins checking markets, notifies user who called for it of that it's starting.

		Args:
			message: The message used to ask the bot to start, used
				to mention the user that it's starting.

		Returns:
			None

		"""
		self._updating = True
		await self._client.send_message(
			message.channel , "Starting {0.author.mention} !".format(message)
			)
		self._logger.info("Starting to check markets.")
		await self.check_markets()


	async def stop_checking_markets(self, message: discord.Message) -> None:
		"""
		Stops checking markets, notifies user who called for it of that it's stopping.

		Args:
			message: The message used to ask the bot to stop, used
				to mention the user that it's stopping.

		Returns:
			None

		"""
		self._logger.info("Stopping checking markets")
		await self._client.send_message(
			message.channel, "Stopping {0.author.mention} !".format(message)
			)
		self._updating = False


	async def greet(self, message: discord.Message) -> None:
		"""
		Greets whoever wants to be greeted !

		Args:
			message: message used to ask for a greet from the bot.
				Used to mention the user for greet.

		Returns:
			None

		"""
		await self._client.send_message(
			message.channel, "Hello {0.author.mention} !".format(message)
			)

	async def exit(self, message: discord.Message) -> None:
		"""
		Shutsdown the bot, logs it, and notifies user who called for it of the exit

		Args:
			message: Discord message used to call for exit.

		Returns:
			None

		"""

		await self._client.send_message(
			message.channel, "Bye {0.author.mention}!".format(message)
			)
		sys.exit()


def get_config() -> dict:
	with open(CONFIG_FILE, "r") as f:
		return json.load(f)


def setup_logging(config: dict) -> None:
	with open(LOGGING_CONFIG, "r") as f:
		log_config = yaml.load(f)

		logging.config.dictConfig(log_config)

		level = logging.INFO if config["debug"] == 0 else logging.DEBUG

		console_logger = logging.getLogger("main")
		console_logger.setLevel(level)

		bot_logger = logging.getLogger("bot")
		bot_logger.setLevel(level)

		console_logger.debug("Set up logging")


if __name__ == '__main__':

	# intialize everything
	client = discord.Client()

	config = get_config()
	setup_logging(config)

	logger = logging.getLogger("main")
	bot = Bot(client=client, config=config, logger=logging.getLogger("bot"))

	# client events
	@client.event
	async def on_ready():
		logger.info("logged in")
		logger.debug("logged in as {0}".format(client.user.name))

	@client.event
	async def on_message(message):
		content = message.content

		# Default greet
		if content.startswith("$greet"):
			await bot.greet(message)

		elif content.startswith("$help"):
			await client.send_message(
				message.channel, "```Starts checking Binance markets and\
				 prints the significant changes.\n" +
					"Args\n" +
					"-h\tPrints this\n" +
					"-i\tPeriod of time spent inbetween checking the markets\n" +
					"-h\tHigh point to print notification\n" +
					"-l\tLow point to print notification"
					)

		elif content.startswith("$start"):
			await bot.start_checking_markets(message)

		elif content.startswith("$stop"):
			await bot.stop_checking_markets(message)

		elif content.startswith("$exit"):
			await bot.exit(message)

	# start
	token = config["token"]
	client.run(token)
