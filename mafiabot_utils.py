import mafia
import errors

import os
import logging
import asyncio
from dotenv import load_dotenv
from enum import Enum
import discord
import gettext

logger = logging.getLogger(__name__)

# set up discord basics
load_dotenv()
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


load_dotenv()
LANG_THEME = os.getenv('LANG_THEME')
lang = LANG_THEME
lang_translations = gettext.translation('utils',
                                        localedir='locales',
                                        languages=[lang])
lang_translations.install()
def _(x): return lang_translations.gettext(x)
# prepare for gettext
# def _(x):   return x


class ErrorContext(Enum):
    JOIN_ATTEMPT = 0,
    START_ATTEMPT = 1
    PRINT_PLAYERS_ATTEMPT = 2,
    PRINT_GAME_STATUS_ATTEMPT = 3


class Channel(Enum):
    OPEN = 0,
    MAFIA = 1,
    COP = 2


class Permissions(Enum):
    ALLOW_VIEW = 0,
    ALLOW_WRITE = 1,
    BLOCK = 2


class MafiaBot():

    def __init__(self, game):
        self.timer = None
        self.game = game
        self.ctx = None
        self.before_warning_time = True
        self.channels = {}
        self.userchannels = {}
        self.fakeuserbots = []

    def get_channels(self, guild=None):
        if not self.channels:
            self.channels = {
                'open_channel': guild.get_channel(OPEN_CHANNEL),
                'open_voice_channel': guild.get_channel(OPEN_VOICE_CHANNEL),
                'mafia_channel': guild.get_channel(MAFIA_CHANNEL),
                'mafia_voice_channel': guild.get_channel(MAFIA_VOICE_CHANNEL),
                'cop_channel': guild.get_channel(COP_CHANNEL),
                'cop_voice_channel': guild.get_channel(COP_VOICE_CHANNEL),
                'category': guild.get_channel(DISCORD_CATEGORY)
            }
        return self.channels

    def get_assigned_channels(self):
        channels = {}
        phase = self.game.status
        hidden_phase = [mafia.GameStatus.NIGHT_TALK,
                        mafia.GameStatus.NIGHT_VOTE]
        open_phase = [mafia.GameStatus.DAY_TALK,
                      mafia.GameStatus.DAY_VOTE]
        if phase in hidden_phase:
            channels.update(
                {Channel.OPEN: self.get_openblocked_channel_users(),
                 Channel.MAFIA: self.get_mafia_channel_users(),
                 Channel.COP: self.get_cop_channel_users()})
        elif phase in open_phase:
            channels.update(
                {Channel.OPEN: self.get_open_channel_users(),
                 # i dont want mafia to see their old discussion
                 Channel.MAFIA: self.get_hidden_channel_users(),
                 # but the cop may, to check their answers
                 # Channel.COP: self.get_cophidden_channel_users()})
                 # what
                 # why did I think that was smart
                 # nonono he aint seeing anything
                 Channel.COP: self.get_hidden_channel_users()})
        return channels

    def get_open_channel_users(self):
        """users and permissions for an open channel"""
        allow_view, allow_write = [], []
        for p in self.game.players:
            # everybody can see
            allow_view.append(p)
            if (p.status == mafia.PlayerStatus.ALIVE):
                # but only living players can write
                allow_write.append(p)
        return {Permissions.ALLOW_VIEW: allow_view,
                Permissions.ALLOW_WRITE: allow_write}

    def get_openblocked_channel_users(self):
        """users and permissions for open channel but currently blocked"""
        allow_view, allow_write = [], []
        for p in self.game.players:
            # everybody can see
            allow_view.append(p)
            # but noone can write, so allow_write stays empty
        return {Permissions.ALLOW_VIEW: allow_view,
                Permissions.ALLOW_WRITE: allow_write}

    def get_hidden_channel_users(self):
        """users and permissions for a completely hidden channel"""
        allow_view, allow_write = [], []
        for p in self.game.players:
            if (p.status != mafia.PlayerStatus.ALIVE):
                # only nonactive players (dead or visiting) can see
                allow_view.append(p)
                # and noone can write, so allow_write stays empty
        return {Permissions.ALLOW_VIEW: allow_view,
                Permissions.ALLOW_WRITE: allow_write}

    def get_mafia_channel_users(self):
        """users and permissions for mafia channel when active"""
        allow_view, allow_write = [], []
        for p in self.game.players:
            if (p.role == mafia.Role.MAFIA or
                p.role == mafia.Role.UNASSIGNED or
                    p.status != mafia.PlayerStatus.ALIVE):
                allow_view.append(p)
                if (p.role == mafia.Role.MAFIA and
                        p.status == mafia.PlayerStatus.ALIVE):
                    allow_write.append(p)
        return {Permissions.ALLOW_VIEW: allow_view,
                Permissions.ALLOW_WRITE: allow_write}

    def get_cop_channel_users(self):
        """users and permissions for cop channel when active"""
        allow_view, allow_write = [], []
        for p in self.game.players:
            if (p.role == mafia.Role.COP or
                p.role == mafia.Role.UNASSIGNED or
                    p.status != mafia.PlayerStatus.ALIVE):
                allow_view.append(p)
                if (p.role == mafia.Role.COP and
                        p.status == mafia.PlayerStatus.ALIVE):
                    allow_write.append(p)
        return {Permissions.ALLOW_VIEW: allow_view,
                Permissions.ALLOW_WRITE: allow_write}

    def get_cophidden_channel_users(self):
        """users and permissions for cop channel when not active"""
        allow_view, allow_write = [], []
        for p in self.game.players:
            if (p.role == mafia.Role.COP or
                p.role == mafia.Role.UNASSIGNED or
                    p.status != mafia.PlayerStatus.ALIVE):
                allow_view.append(p)
        return {Permissions.ALLOW_VIEW: allow_view,
                Permissions.ALLOW_WRITE: allow_write}

    async def timer_start(self, ctx, callmethod):
        if self.timer:
            self.timer.cancel()
        self.before_warning_time = True
        if self.game.status in [mafia.GameStatus.DAY_TALK,
                                mafia.GameStatus.DAY_VOTE]:
            time = WAITING_TIME_DAY_IN_SEC - WARNING_TIMER_IN_SEC
        else:
            time = WAITING_TIME_NIGHT_IN_SEC - WARNING_TIMER_IN_SEC
        self.timer_callmethod = callmethod
        self.ctx = ctx
        self.timer = asyncio.create_task(self.timer_cycle(time))

    async def timer_cycle(self, time):
        await asyncio.sleep(time)
        if self.before_warning_time:
            msg = _('Only') + " " + str(WARNING_TIMER_IN_SEC) + " "
            msg += _('seconds left!')
            if self.game.status in [mafia.GameStatus.DAY_TALK,
                                    mafia.GameStatus.DAY_VOTE]:
                await self.get_channels()['open_channel'].send(msg)
            else:
                await self.get_channels()['mafia_channel'].send(msg)
                await self.get_channels()['cop_channel'].send(msg)
            self.before_warning_time = False
            self.timer = asyncio.create_task(
                self.timer_cycle(WARNING_TIMER_IN_SEC))
        else:
            await self.get_channels()['open_channel'].send(
                _('Time ran out!'))
            await self.timer_callmethod(self.ctx, False, True)  # cycle()
            await self.timer_start(self.ctx, self.timer_callmethod)

    def print_players(self, roles=False):
        try:
            msg = "Players:\n"
            living, dead, unknown = [], [], []
            for p in self.game.players:
                if p.status == mafia.PlayerStatus.ALIVE:
                    living.append(p)
                elif p.status == mafia.PlayerStatus.DEAD:
                    dead.append(p)
                else:
                    unknown.append(p)
            switcher = {
                mafia.PlayerStatus.ALIVE: _('alive'),
                mafia.PlayerStatus.DEAD: _('dead'),
                mafia.PlayerStatus.JOINED: _('waiting')
            }
            for p in living + dead + unknown:  # sort: living first, then dead
                msg += "    - " + str(p.name) + " ("
                msg += switcher.get(p.status, _('unknown status')) + ")"
                if roles:
                    msg += " [" + self.read_role(p.role) + "]"
                msg += "\n"
        except errors.Error as err:
            err.context = ErrorContext.PRINT_PLAYERS_ATTEMPT
            msg = self.error_message(err)
        finally:
            return msg

    def print_game_status(self):
        try:
            msg = self.read_game_status(self.game.status)
        except errors.Error as err:
            err.context = ErrorContext.PRINT_GAME_STATUS_ATTEMPT
            msg = self.error_message(err)
        finally:
            return msg

    def error_message(self, err):
        switcher = {
            errors.AlreadyVotedError: self.already_voted_err,
            errors.CantVoteError: self.cant_vote_err,
            errors.NotVotingScenarioError: self.no_voting_scenario_err,
            errors.NoUniqueWinnerError: self.no_unique_vote_err,
            errors.AlreadyRunningError: self.already_running_err,
            errors.AlreadyJoinedError: self.already_joined_err,
            errors.NotRunningError: self.not_running_err,
            errors.WinnerAlreadyDeadError: self.winner_dead_err,
            errors.Error: self.default_error
        }
        msg = switcher.get(err.__class__)(err)
        return msg

    def add_context(self, err):
        if err.context is None:
            return ""
        else:
            if hasattr(err, 'player'):
                player_str = str(err.player.name)
            else:
                player_str = _('someone')
            switcher = {
                ErrorContext.PRINT_GAME_STATUS_ATTEMPT:
                _('trying to print game status'),
                ErrorContext.PRINT_PLAYERS_ATTEMPT:
                _('trying to print players'),
                ErrorContext.JOIN_ATTEMPT:
                player_str + " " + _('tried to join'),
                ErrorContext.START_ATTEMPT:
                _('trying to start game')
            }
            return " (" + switcher.get(err.context) + ")"

    def default_error(self, err):
        return _('An unidentified error occurred.')

    def cant_vote_err(self, err):
        return err.player.name + " " + _('cannot vote right now.')

    def already_voted_err(self, err):
        return err.player.name + " " + _('already voted.')

    def winner_dead_err(self, err):
        return err.player.name + " " + _('cannot be killed '
                                         'since they already died.')

    def no_voting_scenario_err(self, err):
        return _('There is no vote at the moment.') + self.add_context(err)

    def no_unique_vote_err(self, err):
        if err.vote == mafia.Vote.MAFIA_VOTE:
            return _('The mafia vote did not have a clear result.')
        elif err.vote == mafia.Vote.COP_VOTE:
            return _('The cop vote did not have a clear result.')
        else:
            return _('The vote result was not clear.')

    def already_running_err(self, err):
        return _('The game has already started.') + self.add_context(err)

    def not_running_err(self, err):
        return _('The game is not running.') + self.add_context(err)

    def already_joined_err(self, err):
        return err.player.name + " " + _('already joined.')

    def read_game_status(self, status):
        switcher = {
            mafia.GameStatus.NOT_RUNNING: _('The game is not running.'),
            mafia.GameStatus.DAY_TALK: _("It's day discussion time."),
            mafia.GameStatus.DAY_VOTE: _("It's day voting time."),
            mafia.GameStatus.NIGHT_TALK: _("It's night discussion time."),
            mafia.GameStatus.NIGHT_VOTE: _("It's night voting time.")
        }
        return switcher.get(status)

    def read_role(self, role):
        switcher = {
            mafia.Role.VILLAGER: _('villager'),
            mafia.Role.MAFIA: _('mafioso'),
            mafia.Role.COP: _('cop'),
            mafia.Role.UNASSIGNED: _('unassigned')
        }
        return switcher.get(role)

    async def move_to_their_own_channel(self, guild, member):
        if member.id in self.userchannels:
            await member.move_to(self.userchannels[member.id])
        else:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False),
                member: discord.PermissionOverwrite(
                    read_messages=True, speak=False)
            }
            category = self.get_channels(guild)['category']
            secret_channel = await guild.create_voice_channel(
                _('Your bed'),
                category=category,
                overwrites=overwrites)
            self.userchannels[member.id] = secret_channel
            await member.move_to(self.userchannels[member.id])

    async def remove_userchannels(self, guild):
        for ch in self.userchannels.values():
            await ch.delete()
        self.userchannels.clear()

    # BULLSHIT
    # EINFAHC LASSEN
    async def createfakeuserbots(self):
        if self.fakeuserbots is not None:
            return
        user1 = os.getenv('MAFIA_USER1')
        user2 = os.getenv('MAFIA_USER2')
        user3 = os.getenv('MAFIA_USER3')
        user4 = os.getenv('MAFIA_USER4')
        user5 = os.getenv('MAFIA_USER5')
        fakes = [user1, user2, user3, user4, user5]
        loop = asyncio.get_event_loop()
        for f in fakes:
            if f is None:
                return False
            else:
                self.fakeuserbots.append(discord.Client())
                i = self.fakeuserbots[-1]
                loop.create_task(i.start(f))
