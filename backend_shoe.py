
import tornado
import tornado.websocket
import tornado.httpserver
import requests
import asyncio
import aiohttp
import json
import foot

"""
()
()	Handles requests from bot for data to post. 
()
"""
class CommandHandler:
	def_mooning = 4
	def_free_fall = -10

	def _percent_change(self, new_price, old_price):
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
	def _calc_rsi(self, market: dict) -> int:
		assert len(gains) == len(losses) # Make sure data matches up
		assert len(gains) > 0 # Make sure there's data

		loss = []
		gain = []

		history = market["prices"][-length::1]

		n = len(gains)

		if last_avg_gain:
			average_gain = ( ( last_avg_gain * (n - 1) ) + gains[-1] ) / n 
		else:
			average_gain = sum(gains) / n

		if last_avg_loss:
			average_loss = ( ( last_avg_loss * (n - 1) ) + losses[-1] ) / n
		else:
			average_loss = sum(losses) / n
		
		try:
			RS = average_gain / average_loss
			RSI = 100 - ( 100 / ( 1 + RS ) ) 
		except ZeroDivisionError:
			# No losses at all bb
			RSI = 100

		RSI = int(RSI)
		
		if not ret_averages:
			return RSI
		
		return ( RSI , average_gain , average_loss ) 


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
	def _process_market(self, market_info: dict, mooning: int, free_fall: int) -> str:
		exchange = market_info["exchange"]
		name = market_info["market_name"]
		old_price = market_info["old_price"]
		new_price = market_info["new_price"]

		change = self._percent_change(old_price, new_price)

		if change > mooning:
			return self._get_output([name, "increased by", str(change), "on", market])

		return None	

	async def _get_binance_markets(self, session: aiohttp.ClientSession) -> str:
		async with session.get("https://api.binance.com/api/v1/ticker/allPrices") as resp:
			return await resp.text()

	async def _get_bittrex_markets(self, session: aiohttp.ClientSession) -> str:
		async with session.get("https://bittrex.com/api/v1.1/public/getmarketsummaries") as rsp:
			return await resp.text()

	"""
	()
	()	checks binance markets for price updates, 
	()	if more than mooning/free_fall then flags it and creates output
	()
	()	Returns tuple of outputs & price updates
	()
	"""
	async def _check_binance_markets(self, session: aiohttp.ClientSession, old_markets: dict, mooning: int = def_mooning, free_fall: int = def_free_fall) -> tuple:
		outputs = []
		price_updates = {}

		new_markets = json.loads( await self._get_binance_markets(session) )
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

				out = outputs.append( self._process_market(info, mooning, free_fall) )
				if out:
					outputs.append(out)
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
	async def _check_bittrex_markets(self, session: aiohttp.ClientSession, old_markets: dict, mooning: int = def_mooning, free_fall: int = def_free_fall) -> tuple:
		outputs = []
		price_updates = {}

		new_markets = json.loads( await self._get_binance_markets(session) )
		# get percent change through all the marketspyt
		for i, old_market in enumerate(old_markets["result"]):
			try:
				new_market = new_markets["result"][i]

				old_market_name = old_market["MarketName"]
				new_market_name = new_market["MarketName"]
			except IndexError:
				continue 

			if old_market_name == new_market_name:
				try: 
					old_price = float(old_market["Last"])
					new_price = float(new_market["Last"])
				except:
					continue

				info = {
					"exchange": "Bittrex",
					"market_name": old_market_named,
					"old_price": old_price,
					"new_price": new_price,
					"1h": None,
					"24h": None,
				}

				out = outputs.append( self._process_market(info, mooning, free_fall) )
				if out:
					outputs.append(out)
					price_updates[i] = new_price

		return (outputs, price_updates)


"""
()
() Websocket for communication between the bot and this backend
() 
() Creates datbase client, and command handler. 
()
"""
class MyService(tornado.websocket.WebSocketHandler):
	def __init__(self, host="localhost": str, port=27017: int, database="laughing-chainsaw": str):
		self._mongo_client = mongodb.MongoClient(host, port)
		self._markets = {}
		self._command_handler = CommandHandler()
		self._updating = False
		
		# load db asynchronously fun
		loop = asyncio.get_event_loop()
		future = asyncio.ensure_future(self._load_markets)
		loop.run_until_complete(future)


	"""
	()
	()	** Make Asynchronous
	()
	()	Asynchronously loads the database from bittrex and binance markets.
	()	This loaded data is used to check percent change.
	()
	"""
	async def _load_database(self) -> None:
		markets = {}
		markets["Bittrex"] = json.loads(requests.get("https://bittrex.com/api/v1.1/public/getmarketsummaries").text)
		markets["Binance"] = json.loads(requests.get("https://api.binance.com/api/v1/ticker/allPrices").text)
		posts = self._db.posts
		posts.insert_one(markets)


	def _update_prices(self, price_updates: dict):
		pass

	"""
	()
	()	Checks both bittrex and binance markets, updates prices and sends outputs to websocket.
	()	Does while self._updating is true ever interval minutes. Always does at least once.
	()
	"""
	async def check_markets(self, old_markets: dict, interval: float = 1, mooning: int = def_mooning, free_fall: int = def_free_fall) -> None:
		async with aiohttp.ClientSession() as session:

			# loop through at least once
			while True:
				price_updates = {}

				outputs, price_updates["Bittrex"] = await self._check_bittrex_markets(old_markets["Bittrex"])
				outputs2, price_updates["Binance"] = await self._check_binance_markets(old_markets["Binance"])

				outputs.extend(outputs2)

				self._update_prices(price_updates)

				# upload to websocket
				for out in outputs:
					self.write_message( out )

				# if not continously updating break
				if not self._updating: 
					break

		


	"""
	()
	() Prints open once the websocket is open
	()
	"""
	def open(self) -> None:
		print("WebSocket Opened")


	"""
	()
	() Processes message asynchronously/synchronously from bot in format of:
	() {
	()   method: <name>
	()   args: <arg1>, <arg2>, etc
	() }
	()
	"""
	def on_message(self, message: dict) -> None:
		j = json.loads(message)
		method_name = j["method"]
		args = j.get("args", ())

		method = getattr(self._command_handler, method_name)

		# Fix this
		if inspect.iscoroutinefunction(method):
			loop = asyncio.get_event_loop()
			task = loop.create_task(method(*args))
			task.add_done_callback( lambda res: self.write_message(res.result()))
			future = asyncio.ensure_future(task)

		elif method:
			res = method(*args)
			self.write_message(res)

		res = await method(params[1::1])
		self.write_message(res)

	"""
	()
	() Prints close once the websocket closes
	()
	"""
	def on_close(self) -> None:
		print("WebSocket Closed")

applications = tornado.web.Application([

])

if __name__ == '__main__':
	main()