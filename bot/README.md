# Miss_Pauling

Miss Pauling is a Discord bot for the Team Fortress 2 South Africa community: rsa.tf/discord

## Prerequisites

In order to run Miss Pauling for yourself, with full functionality, you will need:
- Python 3.8+
- A Discord [bot account](https://discordpy.readthedocs.io/en/latest/discord.html)
- An `.env` file places in the projects root directory (example below)
- A TF2 (or SRCDS) server

## Installation

To install Miss Pauling, simply clone this repo, activate the virtual environment and install required dependencies:
```bash
russ@Russ-PC:~$ git clone git@github.com:rsatf/Miss_Pauling.git
russ@Russ-PC:~/Miss_Pauling$ pipenv shell
(Miss_Pauling) russ@Russ-PC:~/Miss_Pauling$ pipenv install
```

## Example `.env`

```
DISCORD_TOKEN="changeme"
PRIMARY_GUILD=1234
PRIMARY_CHANNEL=5678
PUG_CHANNELS='[10101, 110011]'
PUG_SERVERS='[("my.server.com", 27015)]'
PUG_PASSWORDS="['my', 'list', 'of', 'passwords']"
RCON_PASSWORD="rconpass"
MAP_POOL='["cp_badlands", "cp_foundry", "cp_freight_final1"]'
```

## Run

From the repo root directory, activate the python virtual environment and run the bot code as a python module:
```bash
russ@Russ-PC:~/Miss_Pauling$ pipenv shell
(Miss_Pauling) russ@Russ-PC:~/Miss_Pauling$ python3 -m pauling
2020-08-07 19:24:07,483:INFO:pauling.bot: Added cog Pick-up Game
2020-08-07 19:24:07,485:INFO:pauling.bot: Added cog Servers
2020-08-07 19:24:07,486:INFO:pauling.bot: Added cog Extensions
2020-08-07 19:24:07,487:INFO:pauling.bot: Added cog Users
2020-08-07 19:24:07,488:INFO:pauling.cogs.pug: Checking for a server password to reset
2020-08-07 19:24:10,540:INFO:pauling.bot: Logged in as Dev Pauling#7196
```

## Acknowledgements

Thanks to these people for their efforts!
- [Ant Cosentino](https://github.com/skibz) - Guidance & Code review
- [Logan Dam](https://github.com/biltongza) - Code review & code suggestions
- [Emily-Rose Steyn](https://github.com/Emily-RoseSteyn) - Code review