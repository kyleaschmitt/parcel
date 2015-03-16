from functools import wraps
from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed

from log import get_logger
from lib import lib
import time

# Logging
log = get_logger('util')


def get_pbar(title, maxval):
    """Create and initialize a custom progressbar

    :param str title: The text of the progress bar
    "param int maxva': The maximumum value of the progress bar

    """
    pbar = ProgressBar(widgets=[
        title, ' ',
        Bar(marker='#', left='[', right=']'), ' ',
        ETA(), ' ', FileTransferSpeed(), ' '], maxval=maxval)
    pbar.update(0)
    return pbar


def monitor_transfer(client, file_id, total_size):
    pbar = get_pbar('', total_size)
    time.sleep(1)
    while (lib.get_client_margs_live(client.instance)):
        downloaded = lib.get_client_margs_downloaded(client.instance)
        try:
            pbar.update(downloaded)
        except:
            pass
        time.sleep(1)


def print_download_information(file_id, size, name, path):
    log.info('-'*40)
    log.info('Starting download   : {}'.format(file_id))
    log.info('-'*40)
    log.info('File name           : {}'.format(name))
    log.info('Download size       : {}'.format(size))
    log.info('Downloading file to : {}'.format(path))


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
                return func(self, *args, **kwargs)
            except KeyboardInterrupt:
                log.error('KeyboardInterrupt in state {}'.format(self.state))
                self.close()
            log.debug('{}: Exiting state: {}'.format(self, self.state))
        return f
    return wrapper
