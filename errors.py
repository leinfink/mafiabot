class Error(Exception):
    """Base class for other exceptions"""
    def __init__(self, context=None):
        self.context = context


class PlayerError(Error):
    """Errors about some player or their actions"""
    def __init__(self, player=None, context=None):
        self.context = context
        self.player = player


class CantVoteError(PlayerError):
    """Raised when the player can't vote right now"""


class AlreadyVotedError(PlayerError):
    """Raised when the player already voted"""


class AlreadyJoinedError(PlayerError):
    """Raised when the player already joined and can't join again"""


class NotVotingScenarioError(PlayerError):
    """Raised when there is no voting scenario active"""


class AlreadyRunningError(Error):
    """Raised when the action can only be done before the game starts"""


class NotRunningError(Error):
    """Raised when the action can only be done after the game starts"""


class WinnerAlreadyDeadError(PlayerError):
    """Couldnt kill, already dead"""


class WrongVoteError(Error):
    """Couldnt vote"""


class NoUniqueWinnerError(Error):
    """Raised when a vote has more than one winner"""
    def __init__(self, vote=None):
        self.vote = vote

        
class LastDrawnVoteError(NoUniqueWinnerError):
    """Raised when a vote has more than one winner and this triggers
    a vote skip / game cycle"""
