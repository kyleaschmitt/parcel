from functools import wraps
from log import get_logger

# Logging
log = get_logger('util')


def vec(val):
    return val if hasattr(val, '__iter__') else [val]


def state_method(*states):
    """Enter a new state

    :param states:
        A list of str or single str specifying the states that are
        valid preceeding this one

    """

    def wrapper(func, *args, **kwargs):
        @wraps(func)
        def f(self, *args, **kwargs):
            assert self.state in vec(states), \
                'Moving from state <{}> to <{}> is invalid'.format(
                    self.state, func.__name__)
            self.state = func.__name__
            log.debug('{}: Entering state: {}'.format(self, self.state))
            try:
                func(self, *args, **kwargs)
            except KeyboardInterrupt:
                log.error('KeyboardInterrupt in state {}'.format(self.state))
                self.close()
            log.debug('{}: Exiting state: {}'.format(self, self.state))
        return f
    return wrapper
