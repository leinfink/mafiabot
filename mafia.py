import random
import logging
import errors
from enum import Enum, IntEnum

logger = logging.getLogger(__name__)


class GameStatus(IntEnum):
    NOT_RUNNING = -1
    NIGHT_TALK = 0
    NIGHT_VOTE = 0  # actually same as _talk, we only need 2 states, sry
    DAY_TALK = 1
    DAY_VOTE = 1  # same


class Role(Enum):
    UNASSIGNED = 0
    VILLAGER = 1
    MAFIA = 2
    COP = 3


class Vote(Enum):
    MAFIA_VOTE = 0,
    COP_VOTE = 1,
    DAY_VOTE = 2


class VoteResult(Enum):
    UNDERWAY = 0,
    FINISHED = 1,
    FAILED_HALF = 2,
    FAILED_ALL = 3,
    FINISHED_ALL = 4


class VoteConsequence(Enum):
    VILLAGERKILL = 0,
    MAFIAKILL = 1,
    LOOKUP = 2


class Consequence():
    def __init__(self, voteconsequence, target):
        self.voteconsequence = voteconsequence
        self.target = target


class VoteReturnObject():
    def __init__(self, player, target, vote, voteresult,
                 consequence=None,
                 parallel_vote=None):
        self.player = player
        self.target = target
        self.vote = vote
        self.voteresult = voteresult
        self.consequence = consequence
        self.parallel_vote = parallel_vote


class PlayerStatus(Enum):
    ALIVE = 0
    DEAD = 1
    JOINED = 2


class DeathCause(Enum):
    VILLAGER_KILL = 0
    MAFIA_KILL = 1


class Player():
    def __init__(self, ID, name=None, role=Role.UNASSIGNED):
        self.ID = ID
        self.name = name
        self._role = role
        self._status = PlayerStatus.JOINED
        self.last_vote = None
        self.death_cause = None
        logger.debug('Created a player.')

    def __eq__(self, other):
        # players should have a unique ID
        # so we treat players with the same ID as equal
        return self.ID == other.ID

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        self._status = status
        logger.debug(f'Player {self.name} status changed to {self.status}.')

    @property
    def role(self):
        return self._role

    @role.setter
    def role(self, role):
        self._role = role
        logger.debug(f'Player {self.name} role changed to {self.role}.')

    def is_dead(self):
        if self.status == PlayerStatus.DEAD:
            return True
        else:
            return False

    def kill(self, cause):
        self.status = PlayerStatus.DEAD
        self.death_cause = cause
        logger.debug(f'Killed a player by cause of {self.death_cause}')


class Game:
    MAFIA_RATIO = 0.6  # x mafias per players
    COP_RATIO = 0.6  # x cops per players
    MAFIA_AMOUNTS = [0, 1, 1, 1, 2, 2, 2, 3, 3, 3]  # mafia for player counts
    COP_AMOUNTS = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1]  # cops for player counts

    def __init__(self):
        self._status = GameStatus.NOT_RUNNING
        self.players = []
        self.mafia_vote_finished = False
        self.cop_vote_finished = False
        self.day_vote_finished = False
        self.cop_total = 0
        self.mafia_total = 0
        self.villager_total = 0
        logger.debug('Created a game.')

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        self._status = status
        logger.debug(f'Game status set to {self.status}.')

    # Actions

    def join(self, ID, name):
        player = Player(ID, name)
        if player in self.players:
            raise errors.AlreadyJoinedError(player)
        elif self.status != GameStatus.NOT_RUNNING:
            raise errors.AlreadyRunningError
        else:
            self.players.append(player)
        logger.debug('Added a player.')
        return player

    def start(self):
        if self.status != GameStatus.NOT_RUNNING:
            raise errors.AlreadyRunningError
        self.cop_vote_finished = False
        self.mafia_vote_finished = False
        self.day_vote_finished = False
        self.cop_total = 0
        self.villager_total = 0
        self.mafia_total = 0
        self.assign_roles()
        for p in self.players:
            p.status = PlayerStatus.ALIVE
        self.cycle()
        logger.debug('Started the game.')

    def stop(self):
        if self.status == GameStatus.NOT_RUNNING:
            raise errors.NotRunningError
        self.reset()
        logger.debug('Stopped the game.')

    def vote_user(self, p, target, target2=None):
        p = self.players.index(Player(p))
        if (Player(target) not in self.players):
            raise errors.WrongVoteError
        else:
            target = self.players.index(Player(target))
        if self.players[p].last_vote is not None:
            raise errors.AlreadyVotedError(self.players[p])
        if self.status not in [GameStatus.DAY_VOTE, GameStatus.NIGHT_VOTE]:
            # not a voting scenario
            raise errors.NotVotingScenarioError
        if self.status == GameStatus.NIGHT_VOTE:
            if self.players[p].role not in [Role.MAFIA, Role.COP]:
                raise errors.CantVoteError(self.players[p])
            elif (self.players[p].role == Role.MAFIA and
                  self.mafia_vote_finished):
                raise errors.CantVoteError(self.players[p])
            elif (self.players[p].role == Role.COP and
                  self.cop_vote_finished):
                raise errors.CantVoteError(self.players[p])
            elif self.players[p].is_dead():
                raise errors.CantVoteError(self.players[p])
        self.players[p].last_vote = target
        logger.debug(f'{self.players[p].name} voted {target}')
        if self.status == GameStatus.DAY_VOTE:
            votetype = Vote.DAY_VOTE
        elif self.status == GameStatus.NIGHT_VOTE:
            if self.players[p].role == Role.MAFIA:
                votetype = Vote.MAFIA_VOTE
            elif self.players[p].role == Role.COP:
                votetype = Vote.COP_VOTE
        vote_object = VoteReturnObject(self.players[p],
                                       self.players[target],
                                       votetype,
                                       VoteResult.UNDERWAY)
        logger.debug(str(vote_object))
        consequence = None
        # check if everybody voted
        # in that case, execute the votes
        if (vote_object.vote == Vote.DAY_VOTE and
                self.check_votes(Vote.DAY_VOTE)):
            consequence = self.execute_day_votes()
            vote_object.voteresult = VoteResult.FINISHED
            vote_object.consequence = consequence
        elif (vote_object.vote == Vote.MAFIA_VOTE and
              self.check_votes(Vote.MAFIA_VOTE)):
            self.mafia_vote_finished = True
            vote_object.voteresult = VoteResult.UNDERWAY
        elif (vote_object.vote == Vote.COP_VOTE and
              self.check_votes(Vote.COP_VOTE)):
            consequence = self.execute_cop_votes()
            vote_object.voteresult = VoteResult.FINISHED
            vote_object.consequence = consequence
        if self.status == GameStatus.DAY_VOTE:
            if self.day_vote_finished:
                vote_object.voteresult = VoteResult.FINISHED_ALL
                self.cycle()
        elif self.status == GameStatus.NIGHT_VOTE:
            if self.mafia_vote_finished:
                logger.debug('mafia finished')
                if self.cop_vote_finished:
                    logger.debug('mafia+cop finished')
                    vote_object.voteresult = VoteResult.FINISHED_ALL
                    if votetype == Vote.COP_VOTE:
                        logger.debug('parallel vote initiated')
                        con2 = self.execute_mafia_votes()
                        v = VoteReturnObject(None, None,
                                             Vote.MAFIA_VOTE,
                                             vote_object.voteresult,
                                             con2)
                        vote_object.parallel_vote = v
                    elif votetype == Vote.MAFIA_VOTE:
                        consequence = self.execute_mafia_votes()
                        vote_object.consequence = consequence
                    self.cycle()
                else:
                    still_cops_left = False
                    for p in self.players:
                        if p.role == Role.COP and not p.is_dead():
                            still_cops_left = True
                    if still_cops_left is False:
                        vote_object.voteresult = VoteResult.FINISHED_ALL
                        if votetype == Vote.MAFIA_VOTE:
                            consequence = self.execute_mafia_votes()
                            vote_object.consequence = consequence
                        self.cycle()
        return vote_object

    def vote_choice(self, p, choice):
        pass

    # Utils
    def reset(self):
        self.status = GameStatus.NOT_RUNNING
        self.players.clear()

    def assign_roles(self):
        player_total = len(self.players)
        if player_total < len(Game.MAFIA_AMOUNTS):
            mafia_total = Game.MAFIA_AMOUNTS[player_total]
        else:
            mafia_total = int(Game.MAFIA_RATIO * player_total)
        if player_total < len(Game.COP_AMOUNTS):
            cop_total = Game.COP_AMOUNTS[player_total]
        else:
            cop_total = int(Game.COP_RATIO * player_total)
        self.mafia_total = mafia_total
        self.cop_total = cop_total
        mafia_counter, cop_counter = 0, 0

        # assign mafia
        if mafia_total > 0:
            for i in range(0, mafia_total):
                while mafia_counter < i+1:
                    r = random.randint(0, player_total - 1)
                    if self.players[r].role == Role.UNASSIGNED:
                        self.players[r].role = Role.MAFIA
                        mafia_counter += 1

        # assign cops
        if cop_total > 0:
            for i in range(0, cop_total):
                while cop_counter < i+1:
                    r = random.randint(0, player_total - 1)
                    if self.players[r].role == Role.UNASSIGNED:
                        self.players[r].role = Role.COP
                        cop_counter += 1

        # assign villagers
        for p in self.players:
            if p.role == Role.UNASSIGNED:
                self.villager_total += 1
                p.role = Role.VILLAGER

        logger.debug('Roles assigned.')

    def cycle(self):
        if self.status == GameStatus.NOT_RUNNING:
            # if the game wasn't running, go directly to NIGHT_TALK
            self.status = GameStatus.NIGHT_TALK
        elif self.status == GameStatus.DAY_VOTE:
            # if DAY_VOTE is reached, go back to NIGHT_TALK
            self.status = GameStatus.NIGHT_TALK
        else:
            # cycle through game states
            self.status = GameStatus(self.status + 1)
        self.mafia_vote_finished = False
        self.cop_vote_finished = False
        self.day_vote_finished = False

    def check_votes(self, what_to_check):
        if what_to_check == Vote.DAY_VOTE:
            for p in self.players:
                # dead people dont vote
                if p.is_dead():
                    continue
                elif p.last_vote is None:
                    # someone alive did not vote yet
                    return False
            # everyone alive voted
            logger.debug('Day votes complete.')
            return True
        elif what_to_check == Vote.MAFIA_VOTE:
            for p in self.players:
                # deads and non-mafia don't matter
                if p.is_dead() or p.role != Role.MAFIA:
                    continue
                elif (p.role == Role.MAFIA
                      and self.mafia_vote_finished is True):
                    # mafia already voted
                    continue
                elif p.last_vote is None:
                    logger.debug(f'{p.name} didn\'t vote yet.')
                    # someone alive did not vote yet
                    return False
            # everyone alive voted
            logger.debug('Mafia votes complete.')
            return True
        elif what_to_check == Vote.COP_VOTE:
            for p in self.players:
                # deads and non-cops dont matter
                if p.is_dead() or p.role != Role.COP:
                    continue
                elif (p.role == Role.COP
                      and self.cop_vote_finished is True):
                    # cops already voted
                    continue
                elif p.last_vote is None:
                    logger.debug(f'{p.name} didn\'t vote yet.')
                    # someone alive did not vote yet
                    return False
            # everyone alive voted
            logger.debug('Cop votes complete.')
            return True
        else:
            # not a voting scenario
            raise errors.NotVotingScenarioError

    def execute_votes(self):
        if self.status == GameStatus.DAY_VOTE:
            self.execute_day_votes()
        elif self.status == GameStatus.NIGHT_VOTE:
            self.execute_night_votes()
        else:
            # not a voting scenario
            raise errors.NotVotingScenarioError

    def execute_day_votes(self):
        self.day_vote_finished = False
        voted_players = []
        # gather all the votes
        for p in self.players:
            # dead people don't vote
            if p.is_dead():
                continue
            vote = p.last_vote
            if vote is not None:
                voted_players.append(vote)
        # kill the highest voted player, if there is a unique winner
        try:
            target = self.kill_highest_from_voted(voted_players,
                                                  DeathCause.VILLAGER_KILL)
        except errors.NoUniqueWinnerError:
            raise errors.NoUniqueWinnerError(Vote.DAY_VOTE)
        else:
            self.day_vote_finished = True
            consequence = Consequence(VoteConsequence.VILLAGERKILL,
                                      target)
            logger.debug('Day votes executed.')
        finally:
            # clear up votes (even if there was no unique winner)
            # people have to revote
            for p in self.players:
                p.last_vote = None
            if self.day_vote_finished:
                return consequence

    def execute_night_votes(self):
        self.execute_mafia_votes()
        self.execute_cop_votes()
        logger.debug('Night votes executed.')

    def execute_mafia_votes(self):
        voted_players = []
        # gather all the votes
        for p in self.players:
            # only check mafia players' votes
            if p.is_dead() or p.role != Role.MAFIA:
                continue
            vote = p.last_vote
            if vote is not None:
                logger.debug(f'vote counted:{p.name} voted {vote}')
                voted_players.append(vote)
        # kill the highest voted player, if there is a unique winner
        self.mafia_vote_finished = False
        try:
            target = self.kill_highest_from_voted(voted_players,
                                                  DeathCause.MAFIA_KILL)
        except errors.NoUniqueWinnerError:
            raise errors.NoUniqueWinnerError(Vote.MAFIA_VOTE)
        else:
            self.mafia_vote_finished = True
            consequence = Consequence(VoteConsequence.MAFIAKILL,
                                      target)
        finally:
            # clear up votes (even if there was no unique winner)
            # people have to revote
            for p in self.players:
                logger.debug(f'{p.name} role = {p.role}')
                if p.role == Role.MAFIA:
                    p.last_vote = None
            if self.mafia_vote_finished is True:
                return consequence

    def execute_cop_votes(self):
        voted_players = []
        # gather all the votes
        for p in self.players:
            # only check cop players' votes
            if p.is_dead() or p.role != Role.COP:
                continue
            vote = p.last_vote
            if vote is not None:
                logger.debug(f'vote counted:{p.name} voted {vote}')
                voted_players.append(vote)
        self.cop_vote_finished = False
        try:
            target = self.players[self.get_most_common_vote(voted_players)]
            # TODO
            pass
        except errors.NoUniqueWinnerError:
            raise errors.NoUniqueWinnerError(Vote.COP_VOTE)
        else:
            self.cop_vote_finished = True
            consequence = Consequence(VoteConsequence.LOOKUP, target)
        finally:
            # clear up votes (even if there was no unique winner)
            # people have to revote
            for p in self.players:
                if p.role == Role.COP:
                    p.last_vote = None
            if self.cop_vote_finished:
                return consequence

    def kill_highest_from_voted(self, voted_players, kill_cause):
        # count the votes
        win_i = self.get_most_common_vote(voted_players)
        if win_i is not False:
            # there was a unique vote
            # so we can kill someone, yay!
            winner = self.players[win_i]
            if not winner.is_dead():
                winner.kill(kill_cause)
            else:
                raise errors.WinnerAlreadyDeadError(winner)
            return winner
        else:
            # there wasn't a unique winner
            raise errors.NoUniqueWinnerError

    def get_most_common_vote(self, votes):
        vote_count = [0] * len(self.players)
        logger.debug(str(votes))
        for i, v in enumerate(votes):
            vote_count[v] += 1
            logger.debug(f'{i}, {v},{vote_count}')
        highest_i, max = 0, 0
        for i, v in enumerate(vote_count):
            if v > max:
                highest_i = i
                max = v
        for i, v in enumerate(vote_count):
            if v == max and i != highest_i:
                # there were at least 2 highest votes
                return False
        return highest_i
