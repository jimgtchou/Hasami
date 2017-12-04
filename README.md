# laughing-chainsaw
Watches bittrex and binance exchanges then posts on a discord channel what is increasing, by how much, and the exchange that it's increasing on.

## Personal Use
There are two things that you currently need to change. (Lines 8 and 9)
```python
CLIENT_TOKEN = "YOUR_ID_HERE"
CHANNEL_ID = "CHANNEL_ID_HERE"
```
Set `CLIENT_TOKEN` to your personal bot's token, and `CHANNEL_ID` to your personal channel's id.

## TODO
1. Documentation.
2. More modularity.
3. Support for decreasing prices.
4. Support for more exchanges.
