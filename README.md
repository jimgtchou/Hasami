# laughing-chainsaw
Watches bittrex and binance exchanges then posts on a discord channel what is increasing, by how much, and the exchange that it's increasing on.

## Personal Use
There are two things that you currently need to change. (Lines 10-13)
```python
CLIENT_TOKEN = "YOUR_TOKEN_HERE"
CHANNEL_ID = "YOUR_CHANNEL_ID"
MOONING = 4
FREE_FALL = -10	
```
Set `CLIENT_TOKEN` to your personal bot's token, and `CHANNEL_ID` to your personal channel's id.
Whenever a market crosses `MOONING` or `FREE_FALL` it prints it out. These can also be changed!

## TODO (v2.0)
1. Support for more exchanges
2. RSI
3. Graphs of RSI history.
4. Support for other trading tools.
