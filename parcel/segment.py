from intervaltree import Interval, IntervalTree
from multiprocessing import Manager
import os
import tempfile
import pickle

from log import get_logger
from utils import get_pbar
from const import HTTP_CHUNK_SIZE

# Logging
log = get_logger('client')


class SegmentProducer(object):

    def __init__(self, file_id, save_path, load_path, n_procs, size,
                 save_interval=int(1e6)):

        self.save_path = save_path
        self.n_procs = n_procs
        self.size = size
        self.pbar = None
        self.save_interval = save_interval

        # Setup producer
        self.manager = Manager()
        self.q_work = self.manager.Queue()
        self.q_complete = self.manager.Queue()

        # Setup work pool
        self.load_state(load_path, size)
        if self.size_complete == self.size:
            log.info('File already complete.')
            return

        # Divide work among pool
        work_size = self.integrate(self.work_pool)
        self.block_size = work_size / n_procs

        # Reporting
        self.pbar = get_pbar(file_id, size)

        # Schedule work
        self.schedule()

    def integrate(self, itree):
        return sum([i.end-i.begin for i in itree.items()])

    def load_state(self, load_path, size):
        # Establish default intervals
        self.work_pool = IntervalTree([Interval(0, size)])
        self.completed = IntervalTree()
        self.size_complete = 0

        if not os.path.isfile(load_path):
            return

        # If there is a file at load_path, attempt to remove
        # downloaded sections from work_pool
        log.info('Found state file {}, attempting to resume download'.format(
            load_path))
        try:
            with open(load_path, "rb") as f:
                self.completed = pickle.load(f)
            assert isinstance(self.completed, IntervalTree), \
                "Bad save state: {}".format(load_path)
        except Exception as e:
            self.completed = IntervalTree()
            log.error('Unable to resume file state: {}'.format(str(e)))
        else:
            self.size_complete = self.integrate(self.completed)
            for interval in self.completed:
                self.work_pool.chop(interval.begin, interval.end)

    def save_state(self):
        try:
            # Grab a temp file in the same directory (hopefully avoud
            # cross device links) in order to atomically write our save file
            temp = tempfile.NamedTemporaryFile(
                prefix='.parcel_',
                dir=os.path.abspath(os.path.join(self.save_path, os.pardir)),
                delete=False)
            # Write completed state
            pickle.dump(self.completed, temp)
            # Make sure all data is written to disk
            temp.flush()
            os.fsync(temp.fileno())
            temp.close()
            # Rename temp file as our save file
            os.rename(temp.name, self.save_path)
        except KeyboardInterrupt:
            log.warn('Keyboard interrupt. removing temp save file'.format(
                temp.name))
            temp.close()
            os.remove(temp.name)
        except Exception as e:
            log.error('Unable to save state: {}'.format(str(e)))
            raise

    def schedule(self):
        while True:
            interval = self._get_next_interval()
            log.debug('Returning interval: {}'.format(interval))
            if not interval:
                return
            self.q_work.put(interval)

    def _get_next_interval(self):
        intervals = sorted(self.work_pool.items())
        if not intervals:
            return None
        interval = intervals[0]
        start = interval.begin
        end = min(interval.end, start + self.block_size)
        self.work_pool.chop(start, end)
        return Interval(start, end)

    def print_progress(self):
        if not self.pbar:
            return
        try:
            self.pbar.update(self.size_complete)
        except Exception as e:
            log.error('Unable to update pbar: {}'.format(str(e)))

    def is_complete(self):
        return self.integrate(self.completed) == self.size

    def finish_download(self):
        for i in range(self.n_procs):
            self.q_work.put(None)
        if self.pbar:
            self.pbar.finish()

    def wait_for_completion(self):
        try:
            since_save = 0
            while not self.is_complete():
                while since_save < self.save_interval:
                    interval = self.q_complete.get()
                    self.completed.add(interval)
                    if self.is_complete():
                        break
                    this_size = interval.end - interval.begin
                    self.size_complete += this_size
                    since_save += this_size
                    self.print_progress()
                since_save = 0
                self.save_state()
        finally:
            self.finish_download()
