# mafiabot
Discord bot for the party game Mafia (or Werewolves).
Players get automatically assigned to secret (voice+text) channels.

Needs to have a .env file containing the following variables:

    DISCORD_TOKEN=<bot_token>
    DISCORD_GUILD=<server_name>
    DISCORD_OPEN_CHANNEL=<channel id for the villager text channel>
    DISCORD_MAFIA_CHANNEL=<channel id for the mafia text channel>
    DISCORD_COP_CHANNEL=<channel id for the cop text channel> 
    DISCORD_OPEN_VOICE_CHANNEL=<villager voice channel id>
    DISCORD_MAFIA_VOICE_CHANNEL=<mafia voice channel id>
    DISCORD_COP_VOICE_CHANNEL=<cop voice channel id, -1 if none>
    DISCORD_ALIVE_ROLE=<role id>
    DISCORD_DEAD_ROLE=<role id>
    DISCORD_CATEGORY=<id for the 'category channel' containing the game channel>
    WAIT_DAY_SEC=360
    WAIT_NIGHT_SEC=120
    WARNING_TIMER_SEC=30
    LANG_THEME=de-wolf

