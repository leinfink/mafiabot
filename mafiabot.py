import os
import logging
# import logging_tree
# import datetime
import gettext

from dotenv import load_dotenv

import discord
from discord.ext import commands

# import the mafia game logic module
import mafia

# import the mafiabot utils module
from mafiabot_utils import MafiaBot, ErrorContext, Channel, Permissions

load_dotenv()
LANG_THEME = os.getenv('LANG_THEME')
lang = LANG_THEME
lang_translations = gettext.translation('base',
                                        localedir='locales',
                                        languages=[lang])
lang_translations.install()
def _(x): return lang_translations.gettext(x)
# def _(x): return x


# set up logging
# first, our own logs
logger = logging.getLogger(__name__)  # get logger for this module
logger.setLevel(logging.DEBUG)  # logging level
handler = logging.StreamHandler()
logger.addHandler(handler)
# get mafia.py logger
mafialogger = logging.getLogger('mafia')
mafialogger.setLevel(logging.DEBUG)
mafialogger.addHandler(handler)
# get mafiabot_utils.py logger
utilslogger = logging.getLogger('mafiabot_utils')
utilslogger.setLevel(logging.DEBUG)
utilslogger.addHandler(handler)
# finally discord.py logs
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING)
discord_logger.addHandler(handler)

# logging_tree to help with logging config
# logging_tree.printout()

# set up discord basics

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
OPEN_CHANNEL = int(os.getenv('DISCORD_OPEN_CHANNEL'))
MAFIA_CHANNEL = int(os.getenv('DISCORD_MAFIA_CHANNEL'))
COP_CHANNEL = int(os.getenv('DISCORD_COP_CHANNEL'))
OPEN_VOICE_CHANNEL = int(os.getenv('DISCORD_OPEN_VOICE_CHANNEL'))
MAFIA_VOICE_CHANNEL = int(os.getenv('DISCORD_MAFIA_VOICE_CHANNEL'))
COP_VOICE_CHANNEL = int(os.getenv('DISCORD_COP_VOICE_CHANNEL'))
ALIVE_ROLE = int(os.getenv('DISCORD_ALIVE_ROLE'))
DEAD_ROLE = int(os.getenv('DISCORD_DEAD_ROLE'))
DISCORD_CATEGORY = int(os.getenv('DISCORD_CATEGORY'))
WAITING_TIME_DAY_IN_SEC = int(os.getenv('WAIT_DAY_SEC'))
WAITING_TIME_NIGHT_IN_SEC = int(os.getenv('WAIT_NIGHT_SEC'))
WARNING_TIMER_IN_SEC = int(os.getenv('WARNING_TIMER_SEC'))

BOTNAME = _('mafiabot')

USEFAKEUSERBOTS = False

# init the bot
bot = commands.Bot(command_prefix='!')


# logging function for bot commands
def cmdlog(ctx):
    logger.info(_('command "') + ctx.command.name + '" ' +
                _('invoked by ') + ctx.author.name)


def game_running(ctx):
    return myGame.status != mafia.GameStatus.NOT_RUNNING


@bot.check
async def globally_block_dms(ctx):
    # only accept if sent from within a guild, not DMs
    return ctx.guild is not None


@bot.check
async def accepted_channels(ctx):
    # only accept if sent from within one of our channels
    channels = myMafiaBot.get_channels(ctx.guild).values()
    logger.debug(str(channels))
    logger.debug(str(ctx.channel))
    return (ctx.channel in channels)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name=_('Mafia')))
    logger.info(f'{bot.user.name} ' + _('has connected to Discord!'))
    guild = discord.utils.get(bot.guilds, name=GUILD)
    logger.info(f'{bot.user.name} ' +
                _('is connected to the following guild:') + '\n'
                f'    {guild.name}(id: {guild.id})')
    await guild.get_member(bot.user.id).edit(
        nick=BOTNAME + " [" +
        print_bot_nick(myGame.status)
        + "]")
    if USEFAKEUSERBOTS:
        logger.warning('WLL CREATE FAKE USER BOTS FOR USE IN'
                       'HIDDEN CHANNELS')
        await myMafiaBot.createfakeuserbots()
    await reset_channel_permissions(None, guild=guild)
    # await guild.get_role(ALIVE_ROLE).edit(name=_('Warten auf Spielbeginn'))


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # important, without this bot commands wont work!
    await bot.process_commands(message)


@bot.command(name=_('join'), help=_('Join a game.'))
async def join(ctx):
    cmdlog(ctx)
    try:
        name = ctx.author.nick if ctx.author.nick else ctx.author.name
        player = myGame.join(ctx.author.id, name)
    except mafia.Error as err:
        logger.exception(_('Failed to join'))
        err.context = ErrorContext.JOIN_ATTEMPT
        name = ctx.author.nick if ctx.author.nick else ctx.author.name
        err.player = mafia.Player(ctx.author.id, name)
        msg = myMafiaBot.error_message(err)
        logger.warning(msg)
        await ctx.send(msg)
    else:
        await assign_discord_role(ctx, player)
        msg = name + " " + _('joined the game.')
        logger.info(msg)
        await ctx.send(msg)
        # await send_status_update(ctx,
        #                         game_status=True,
        #                         player_status=True,
        #                         player_roles=True)

@bot.command(name=_('rules'), help=_('Read the rules.'))
async def rules(ctx):
    msg = _("""— Some basics: ```There\'s villagers, mafia, and cops.```""")
    msg += _("""``` The only command you need to  play is !vote <user> (or just ping them, <@user>).``````You can vote as soon as you like, but you can\'t take it back. For a vote to go through, everybody needs to have voted and there should be a clear \"winner\". ``````Daytime will last a maximum
        of""")

    msg += " "
    msg += str(WAITING_TIME_DAY_IN_SEC/60)
    msg += _(""" minutes, if there is no result by then, your action goes to waste.
        Nighttime lasts """)
    msg += str(WAITING_TIME_NIGHT_IN_SEC/60)
    msg += _(""" minutes.``````In the member list
        on the right, you can see who\'s alive and who\'s dead. If this
        doesn\'t update, use !status to print the current status in the chat.
        In night channels, 1) the member list doesn\'t show everbody, and 2)
        you don\'t have ping autocomplete. Make sure to type their names
        right (better drop the @, since it doesn\'t work with nicknames).```
        \nGo join the village voice channel, then close your eyes!\n""")
    await ctx.send(msg)

@bot.command(name=_('start'), help=_('Start the game.'))
async def start(ctx):
    cmdlog(ctx)
    try:
        if len(myGame.players) < 2:
            raise mafia.Error
        myGame.start()
    except mafia.Error as err:
        # err.context = ErrorContext.START_ATTEMPT
        logger.exception(_('Failed to start'))
        msg = myMafiaBot.error_message(err)
        logger.warning(msg)
        await ctx.send(msg)
    else:
        logger.info(_('Game started!'))
        msg = _('**Game started!**')
        msg += _("""— Some basics: ```There\'s villagers, mafia, and cops.```""")
        msg += _("""``` The only command you need to  play is !vote <user> (or just ping them, <@user>).``````You can vote as soon as you like, but you can\'t take it back. For a vote to go through, everybody needs to have voted and there should be a clear \"winner\". ``````Daytime will last a maximum
        of""")

        msg += " "
        msg += str(WAITING_TIME_DAY_IN_SEC/60)
        msg += _(""" minutes, if there is no result by then, your action goes to waste.
        Nighttime lasts """)
        msg += str(WAITING_TIME_NIGHT_IN_SEC/60)
        msg += _(""" minutes.``````In the member list
        on the right, you can see who\'s alive and who\'s dead. If this
        doesn\'t update, use !status to print the current status in the chat.
        In night channels, 1) the member list doesn\'t show everbody, and 2)
        you don\'t have ping autocomplete. Make sure to type their names
        right (better drop the @, since it doesn\'t work with nicknames).```
        \nGo join the village voice channel, then close your eyes!\n""")
        mafios = _('mafioso') if myGame.mafia_total == 1 else _('mafiosi')
        cops = _('cop') if myGame.cop_total == 1 else _('cops')
        villager_sl = myGame.villager_total == 1
        villagers = _('villager') if villager_sl else _('villagers')
        msg += "\n" + _('**There is') + " " + str(myGame.mafia_total)
        msg += " " + mafios + ", " + str(myGame.cop_total) + " "
        msg += cops + " and " + str(myGame.villager_total) + " "
        msg += villagers + ".**"
        await change_bot_name(ctx)
        await ctx.send(msg)
        # await ctx.guild.get_role(ALIVE_ROLE).edit(name=_('Lebendig'))
        await normal_game_update(ctx, show_status=False,
                                 show_channel_list=True)

        await send_status_update(ctx,
                                 game_status=True,
                                 player_status=False,
                                 player_roles=False,
                                 channel=myMafiaBot.get_channels(ctx.guild)
                                 ['open_channel'])


@bot.command(name=_('stop'), help=_('Stop the game.'))
@commands.is_owner()
async def stop(ctx):
    cmdlog(ctx)
    try:
        await reset_channel_permissions(ctx)
        await remove_all_discord_roles(ctx)
        await myMafiaBot.remove_userchannels(ctx.guild)
        myGame.stop()
    except mafia.Error as err:
        logger.exception(_('Failed to stop'))
        msg = myMafiaBot.error_message(err)
        logger.warning(msg)
        await ctx.send(msg)
    else:
        msg = _('Game stopped!')
        logger.info(msg)
        myMafiaBot.timer.cancel()
        # bot.get_cog('MyTimer').cancel_timer()
        await change_bot_name(ctx)
        await ctx.send(msg)
        # await ctx.guild.get_role(ALIVE_ROLE).edit(
        #    name=_('Warten auf Spielbeginn'))
        await send_status_update(ctx,
                                 game_status=True,
                                 player_status=False)


@bot.command(name=_('next'), help=_('Go to the next game phase.'))
@commands.check(game_running)
@commands.is_owner()
async def next(ctx):
    cmdlog(ctx)
    await cycle(ctx)


async def cycle(ctx, restart_timer=True, check_mafia=False):
    try:
        if check_mafia:
            logger.debug('mafiacheck')
            if myGame.status == mafia.GameStatus.NIGHT_VOTE:
                logger.debug('nightvotechek')
                if myGame.mafia_vote_finished:
                    logger.debug('mafiavotefinishedcheck')
                    con = myGame.execute_mafia_votes()
                    mafia_return = mafia.VoteReturnObject(
                        None,
                        None,
                        mafia.Vote.MAFIA_VOTE,
                        mafia.VoteResult.FINISHED_ALL,
                        con
                    )
                    logger.debug(con)
                    await finished_vote_compute(ctx, "", mafia_return)
        myGame.cycle()
    except mafia.Error as err:
        logger.exception(_('Failed to cycle.'))
        msg = myMafiaBot.error_message(err)
        logger.warning(msg)
        await ctx.send(msg)
    else:
        logger.info(_('Cycled game phase.'))
        await change_bot_name(ctx)
        logger.debug(restart_timer)
        await normal_game_update(ctx, restart_timer=restart_timer)
        await send_status_update(ctx,
                                 game_status=True,
                                 channel=myMafiaBot.get_channels(ctx.guild)
                                 ['open_channel'])


async def finished_vote_compute(ctx, msg, vote_return_object, update=True):
    logger.debug('in finish_vote')
    # everbody voted, votes got executed
    switcher = {
        mafia.Vote.DAY_VOTE: _('Villager vote ended.'),
        mafia.Vote.MAFIA_VOTE: _('The mafia has decided.'),
        mafia.Vote.COP_VOTE: _('The cops have made their choice.')
    }
    msg2 = "\n" + switcher.get(vote_return_object.vote)
    switcher = {
        mafia.VoteConsequence.VILLAGERKILL: _('They decided to lynch'),
        mafia.VoteConsequence.MAFIAKILL: _('They decided to kill'),
        mafia.VoteConsequence.LOOKUP: _('They decided to look at')
    }
    msg2 += "\n**" + switcher.get(vote_return_object.consequence.
                                  voteconsequence)
    msg2 += " " + vote_return_object.consequence.target.name + "!**"
    logger.debug(msg2)
    await change_bot_name(ctx)
    if vote_return_object.vote == mafia.Vote.COP_VOTE:
        msg3 = "\n" + _('They are a')
        msg3 += " " + myMafiaBot.read_role(
            vote_return_object.consequence.target.role) + "."
        await ctx.send(msg+msg2+msg3)
    if vote_return_object.vote == mafia.Vote.MAFIA_VOTE:
        if msg != "":
            await ctx.send(msg)
        logger.debug('mafiavotesending')
        await myMafiaBot.get_channels(ctx.guild)['open_channel'].send(
                msg2)
    if vote_return_object.vote == mafia.Vote.DAY_VOTE:
        await myMafiaBot.get_channels(ctx.guild)['open_channel'].send(
                    msg+msg2)
    if update and (vote_return_object.voteresult ==
                   mafia.VoteResult.FINISHED_ALL):
        await normal_game_update(ctx, show_status=True)


@bot.command(name=_('status'))
@commands.check(game_running)
async def status(ctx):
    # msg = myMafiaBot.print_game_status() + "\n"
    msg = myMafiaBot.print_players() + "\n"
    await ctx.send(msg)

@bot.command(name=_('vote'), help=_('Vote for a user.'))
@commands.check(game_running)
async def vote(ctx, member: discord.Member):
    cmdlog(ctx)
    try:
        vote_return_object = myGame.vote_user(ctx.author.id, member.id)
    except mafia.Error as err:
        logger.exception(_('Failed to vote.'))
        msg = myMafiaBot.error_message(err)
        logger.warning(msg)
        await ctx.send(msg)
    else:
        msg = vote_return_object.player.name + " " + _('voted for')
        msg += " " + vote_return_object.target.name
        logger.info(_('Voted.'))
        if vote_return_object.voteresult in [mafia.VoteResult.FINISHED,
                                             mafia.VoteResult.FINISHED_ALL]:
            parallel = False
            if vote_return_object.parallel_vote is not None:
                logger.debug('parallel vote!')
                await finished_vote_compute(ctx, msg,
                                            vote_return_object.parallel_vote,
                                            update=True)
                parallel = True
            await finished_vote_compute(ctx, msg,
                                        vote_return_object, not parallel)
        elif vote_return_object.voteresult == mafia.VoteResult.UNDERWAY:
            # send to same channel as the last vote
            await ctx.send(msg)


def print_bot_nick(status):
    switcher = {
        mafia.GameStatus.DAY_TALK: _('Day'),
        mafia.GameStatus.DAY_VOTE: _('Day'),
        mafia.GameStatus.NIGHT_TALK: _('Night'),
        mafia.GameStatus.NIGHT_VOTE: _('Night'),
        mafia.GameStatus.NOT_RUNNING: _('Not running')
    }
    return switcher.get(status)


async def change_bot_name(ctx):
    # only if we changed to the following statuses
    if myGame.status in [mafia.GameStatus.DAY_TALK,
                         mafia.GameStatus.NIGHT_TALK,
                         mafia.GameStatus.NOT_RUNNING]:
        await ctx.guild.get_member(bot.user.id).edit(
            nick=BOTNAME + " [" +
            print_bot_nick(myGame.status)
            + "]")


def game_over():
    alive_mafia = []
    alive_villagers = []
    for p in myGame.players:
        if not p.is_dead():
            if p.role == mafia.Role.MAFIA:
                alive_mafia.append(p)
            else:
                alive_villagers.append(p)
    if not alive_mafia:
        return mafia.Role.VILLAGER
    if not alive_villagers:
        return mafia.Role.MAFIA
    return False


async def normal_game_update(ctx, show_status=False,
                             show_channel_list=False,
                             restart_timer=True):
    game_result = game_over()
    if game_result:
        msg = _('Game over!')
        if game_result == mafia.Role.VILLAGER:
            msg += "\n**" + _('The villagers won!') + "**\n"
        elif game_result == mafia.Role.MAFIA:
            msg += "\n**" + _('The mafia won!') + "**\n"
        msg += myMafiaBot.print_players(True)
        await myMafiaBot.get_channels(ctx.guild)['open_channel'].send(
            msg)
        myMafiaBot.timer.cancel()
        await stop(ctx)
        return
    # check if we need to reassign roles because of a 'location change'
    if myGame.status in [mafia.GameStatus.DAY_TALK,
                         mafia.GameStatus.NIGHT_TALK]:
        async with myMafiaBot.get_channels(ctx.guild)['open_channel'].typing():
            await assign_channels(ctx)
            if show_channel_list:
                await myMafiaBot.get_channels(ctx.guild)['open_channel'].send(
                    _('The mafia gather in ') +
                    myMafiaBot.get_channels(
                        ctx.guild)['mafia_channel'].mention + "\n" +
                    _('The cops gather in ') +
                    myMafiaBot.get_channels(
                        ctx.guild)['cop_channel'].mention
                )
            # assign roles and send the welcome msgs
            # in the respective channels
            await assign_all_discord_roles(ctx)
            await send_channel_notifs(ctx)
        # status also only gets shown after location change
        # and if wanted
        if show_status:
            await send_status_update(ctx,
                                     game_status=True,
                                     player_status=False,
                                     player_roles=False,
                                     channel=myMafiaBot.get_channels(ctx.guild)
                                     ['open_channel'])
        logger.debug(f'restart timer in normalgame:{restart_timer}')
        if restart_timer:
            await myMafiaBot.timer_start(ctx, cycle)
            # await bot.get_cog('MyTimer').start_timer(ctx, skip_next=True)


async def send_channel_notifs(ctx):
    channels = myMafiaBot.get_channels(ctx.guild)
    # open_channel = channels['open_channel']
    mafia_channel = channels['mafia_channel']
    cop_channel = channels['cop_channel']
    # everyone_mention = ctx.guild.default_role.name

    if myGame.status in [mafia.GameStatus.NIGHT_TALK]:
        await mafia_channel.send(_('Prepare to commit a heinous crime!'))
        await cop_channel.send(_('Prepare to show off '
                                 'your investigative prowess!'))
    # elif myGame.status in [mafia.GameStatus.DAY_TALK,
    #                       mafia.GameStatus.NOT_RUNNING]:
        # await open_channel.send(_('Discuss.'))


async def assign_all_discord_roles(ctx):
    for p in myGame.players:
        # alive or something else goes in the same role
        await assign_discord_role(ctx, p)


async def remove_all_discord_roles(ctx=None, guild=None):
    if ctx and not guild:
        guild = ctx.guild
    for p in myGame.players:
        await guild.get_member(p.ID).remove_roles(
            guild.get_role(ALIVE_ROLE),
            guild.get_role(DEAD_ROLE))


async def assign_discord_role(ctx, player):
    p = player
    if p.status != mafia.PlayerStatus.DEAD:
        await ctx.guild.get_member(p.ID).add_roles(
                ctx.guild.get_role(ALIVE_ROLE))
        await ctx.guild.get_member(p.ID).remove_roles(
            ctx.guild.get_role(DEAD_ROLE))
    if p.status == mafia.PlayerStatus.DEAD:
        await ctx.guild.get_member(p.ID).add_roles(
                ctx.guild.get_role(DEAD_ROLE))
        await ctx.guild.get_member(p.ID).remove_roles(
            ctx.guild.get_role(ALIVE_ROLE))


async def set_channel_permits(guild, channel, permits=None,
                              block_everyone=True, voice=False):
    overwrites = {}

    if not voice:
        if block_everyone:
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                read_messages=False,
                send_messages=False)
        if permits is not None:
            for p in permits[Permissions.ALLOW_VIEW]:
                allow_write = (p in permits[Permissions.ALLOW_WRITE])
                overwrites[guild.get_member(p.ID)] = (
                    discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=allow_write))
    else:
        if block_everyone:
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                view_channel=False,
                read_messages=False,
                connect=False,
                speak=False)
        if permits is not None:
            for p in permits[Permissions.ALLOW_VIEW]:
                allow_speak = (p in permits[Permissions.ALLOW_WRITE])
                logger.debug(f'{p.name} allowed to speak in {channel.name}?:'
                             f'{allow_speak}')
                overwrites[guild.get_member(p.ID)] = (
                    discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        connect=True,
                        speak=allow_speak))
    await channel.edit(overwrites=overwrites)
    logger.debug(f'Set channel permits (voice={voice}) '
                 f'for {channel.name} (id:{channel.id})')


async def move_users_to_voice_channels(guild, channel_permits):
    open_channel = myMafiaBot.get_channels(guild)['open_voice_channel']
    mafia_channel = myMafiaBot.get_channels(guild)['mafia_voice_channel']
    cop_channel = myMafiaBot.get_channels(guild)['cop_voice_channel']

    if myGame.status in [mafia.GameStatus.NOT_RUNNING,
                         mafia.GameStatus.DAY_TALK,
                         mafia.GameStatus.DAY_VOTE]:
        # cant do this if we have to kick villagers when night starts
        # only do it if we create seperate channels for them
        # else we would only be able to move mafia and cops back
        # since you cant move if not connected
        # and it would be noticeable who is not a villager

        await move_players_back_to_open(guild,
                                        channel_permits[Channel.OPEN]
                                        [Permissions.ALLOW_VIEW])
        pass
    elif myGame.status in [mafia.GameStatus.NIGHT_TALK,
                           mafia.GameStatus.NIGHT_VOTE]:
        if open_channel:
            # kick every person that doesn't have another channel
            can_move_to_channels = []
            if mafia_channel:
                can_move_to_channels += channel_permits[
                    Channel.MAFIA][Permissions.ALLOW_VIEW]
            if cop_channel:
                can_move_to_channels += channel_permits[
                    Channel.COP][Permissions.ALLOW_VIEW]
            for m in open_channel.members:
                if mafia.Player(m.id) not in can_move_to_channels:
                    # definitely kick nonplaying people
                    if mafia.Player(m.id) not in myGame.players:
                        await m.move_to(None)
                        continue
                    # maybe too slow?
                    await myMafiaBot.move_to_their_own_channel(guild, m)
                    # maybe just everyone instead
                    # await m.move_to(None)

        if mafia_channel:
            for p in channel_permits[Channel.MAFIA][Permissions.ALLOW_VIEW]:
                m = guild.get_member(p.ID)
                if m.voice is not None:
                    # we can only move if user is already connected
                    await m.move_to(mafia_channel)
        if cop_channel:
            for p in channel_permits[Channel.COP][Permissions.ALLOW_VIEW]:
                m = guild.get_member(p.ID)
                if m.voice is not None:
                    # we can only move if user is already connected
                    await m.move_to(cop_channel)


async def OLDmove_to_their_own_channel(guild, member):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True,
                                            speak=False)
    }
    category = myMafiaBot.get_channels(guild)['category']
    secret_channel = await guild.create_voice_channel(_('Your bed'),
                                                      category=category,
                                                      overwrites=overwrites)
    myNewChannels.append(secret_channel)
    await member.move_to(secret_channel)


async def move_players_back_to_open(guild, permits):
    if myMafiaBot.get_channels(guild)['open_voice_channel']:
        for p in permits:
            m = guild.get_member(p.ID)
            if m.voice is not None:
                # we can only move if user is already connected
                await guild.get_member(p.ID).move_to(
                    myMafiaBot.get_channels(guild)['open_voice_channel'])
    # for ch in myNewChannels:
    #    await ch.delete()
    #    myNewChannels.remove(ch)


async def assign_channels(ctx):
    channel_permits = myMafiaBot.get_assigned_channels()
    guild = ctx.guild
    channels = myMafiaBot.get_channels(guild)

    if channels['open_channel']:
        await set_channel_permits(guild, channels['open_channel'],
                                  channel_permits[Channel.OPEN],
                                  voice=False)
    if channels['open_voice_channel']:
        if myGame.status in [mafia.GameStatus.DAY_TALK,
                             mafia.GameStatus.DAY_VOTE]:
            permits = channel_permits[Channel.OPEN]
        else:
            # we need to kick everybody out of voice
            # to make sure people can't know who's mafia
            permits = None
        await set_channel_permits(guild, channels['open_voice_channel'],
                                  permits,
                                  voice=True)
    if channels['mafia_channel']:
        await set_channel_permits(guild, channels['mafia_channel'],
                                  channel_permits[Channel.MAFIA],
                                  voice=False)
    if channels['mafia_voice_channel']:
        await set_channel_permits(guild, channels['mafia_voice_channel'],
                                  channel_permits[Channel.MAFIA],
                                  voice=True)
    if channels['cop_channel']:
        await set_channel_permits(guild, channels['cop_channel'],
                                  channel_permits[Channel.COP],
                                  voice=False)
    if channels['cop_voice_channel']:
        await set_channel_permits(guild, channels['cop_voice_channel'],
                                  channel_permits[Channel.COP],
                                  voice=True)
    await move_users_to_voice_channels(guild, channel_permits)


async def reset_channel_permissions(ctx=None, guild=None):
    if ctx and not guild:
        guild = ctx.guild
    channels = myMafiaBot.get_channels(guild)

    if channels['open_channel']:
        await sync_channel_permissions(channels['open_channel'])
    if channels['open_voice_channel']:
        await sync_channel_permissions(channels['open_voice_channel'])
    if channels['mafia_channel']:
        await reset_permission_with_hiding(channels['mafia_channel'])
    if channels['mafia_voice_channel']:
        await reset_permission_with_hiding(channels['mafia_voice_channel'])
    if channels['cop_channel']:
        await reset_permission_with_hiding(channels['cop_channel'])
    if channels['cop_voice_channel']:
        await reset_permission_with_hiding(channels['cop_voice_channel'])
    logger.info(_('Channel permissions reset.'))


async def hide_channel_for_default(channel):
    # read_messages also works for voice channels
    await channel.set_permissions(channel.guild.default_role,
                                  read_messages=False,
                                  send_messages=False)


async def sync_channel_permissions(channel):
    await channel.edit(sync_permissions=True)


async def reset_permission_with_hiding(channel):
    # first open up
    await sync_channel_permissions(channel)
    # then hide
    await hide_channel_for_default(channel)


async def send_status_update(ctx,
                             game_status=True,
                             player_status=False,
                             player_roles=False,
                             channel=None):
    status = ""
    if game_status:
        status += myMafiaBot.print_game_status() + "\n"
    if player_status:
        status += myMafiaBot.print_players(player_roles) + "\n"
    if channel is not None:
        await channel.send(status)
    else:
        await ctx.send(status)
    logger.info(_('Sent status update.'))

# start new mafia game
myNewChannels = []
myGame = mafia.Game()
myMafiaBot = MafiaBot(myGame)
# bot.add_cog(MyTimer(bot))
# run the bot
logger.info(_('Connecting to Discord...'))
bot.run(TOKEN)
