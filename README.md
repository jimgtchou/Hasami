# laughing-chainsaw
laughing-chainsaw is a discord bot that monitors bittrex and binance exchanges for significant changes in price / significant RSI values and prints it out in a specified channel.

## Usage
For basic personal use you need to set `"token"` to your personal bot's token, and `"update_channel"` to the channel the bot should print updates to in `config.json`

```json
"token": "your token",
"update_channel": "your channel id",
```

### Requirements
- Python >= 3.5.3
- [discord](https://github.com/Rapptz/discord.py)
- [aiohttp](https://github.com/aio-libs/aiohttp)


### Configuration
All configuration takes place within `config.json`

```json
{
	"token": "your token",
	"update_channel": "your channel id",
	"free_fall": -5,
	"mooning": 5,
	"over_bought": 80,
	"over_sold": 20,
	"update_interval": 1,
}
```

| Option | Description | 
| --- | --- | 
| `token` | The bot's token to use to create connection with discord | 
| `update_channel` | The channel the bot will print updates to |
| `free_fall` | Low value to flag market for printing **(Price Change)**|
| `mooning` | High value to flag market for printing **(Price Change)** | 
| `over_bought` | Over bought value to flag market for printing **(RSI)** |
| `over_sold` | Over sold value to flag market for printing **(RSI)** | 
| `update_interval` | Delay between each time it checks the markets (in minutes) |

### What it's doing
When a market's growth/decline is greater than or equal to `mooning` or `free_fall`, the bot flags it and prints an update according to this format.
```
<market_name> changed by <change> on <exchange>
```

When a market's rsi value is greater than or equal to `over_bought` or `over_sold`, the bot flags it and prints an update according to this format.
```
<market_name> RSI: <rsi>
```

## TODO (v2.0)
1. Support for more exchanges.
2. Graphs of RSI history.
3. Support for other trading tools.
4. Price display under `playing` on bot.

