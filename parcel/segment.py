from intervaltree import Interval, IntervalTree
import os
import tempfile
import pickle

if os.name == 'nt':
    WINDOWS = True
    from Queue import Queue
else:
    # if we are running on a posix system, then we will be
    # communicating across processes, and will need
    # multiprocessing manager
    from multiprocessing import Manager
    WINDOWS = False

from log import get_logger
from utils import get_pbar, md5sum, mmap_open, set_file_length,\
    get_file_type, STRIP
from progressbar import ProgressBar, Percentage, Bar, ETA

log = get_logger('segment')


class SegmentProducer(object):

    def __init__(self, file_id, file_path, save_path, load_path, n_procs, size,
                 save_interval=int(1e6), check_segment_md5sums=False):

        self.file_id = file_id
        self.file_path = file_path
        self.save_path = save_path
        self.n_procs = n_procs
        self.size = size
        self.pbar = None
        self.save_interval = save_interval
        self.check_segment_md5sums = check_segment_md5sums
        self.is_regular_file = False

        # Setup producer
        if WINDOWS:
            self.q_work = Queue()
            self.q_complete = Queue()
        else:
            manager = Manager()
            self.q_work = manager.Queue()
            self.q_complete = manager.Queue()

        # Setup work pool
        self.load_state(load_path, size)
        if self.is_complete():
            log.info('File already complete.')
            return

        # Divide work among pool
        work_size = self.integrate(self.work_pool)
        self.block_size = work_size / n_procs

        # Reporting
        self.pbar = get_pbar(file_id, size)

        # Create file if needed and schedule work
        try:
            set_file_length(self.file_path, self.size)
        except:
            log.warn(STRIP(
                """Unable to set file length. File appears to
                be a {} file, attempting to proceed.
                """.format(get_file_type(self.file_path))))
            self.is_regular_file = False
        self.schedule()

    def integrate(self, itree):
        return sum([i.end-i.begin for i in itree.items()])

    def validate_segment_md5sums(self):
        if not self.check_segment_md5sums:
            return True
        intervals = sorted(self.completed.items())
        pbar = ProgressBar(widgets=[
            'Checksumming {}:'.format(self.file_id), Percentage(), ' ',
            Bar(marker='#', left='[', right=']'), ' ', ETA()])
        with mmap_open(self.file_path) as data:
            for interval in pbar(intervals):
                log.debug('Checking segment md5: {}'.format(interval))
                if not interval.data or 'md5sum' not in interval.data:
                    log.error(STRIP(
                        """User opted to check segment md5sums on restart.
                        Previous download did not record segment
                        md5sums (--no-segment-md5sums)."""))
                    return
                chunk = data[interval.begin:interval.end]
                checksum = md5sum(chunk)
                if checksum != interval.data.get('md5sum'):
                    log.warn('Redownloading corrupt segment {}, {}.'.format(
                        interval, checksum))
                    self.completed.remove(interval)

    def load_state(self, load_path, size):
        # Establish default intervals
        self.work_pool = IntervalTree([Interval(0, size)])
        self.completed = IntervalTree()
        self.size_complete = 0

        if not os.path.isfile(load_path) and os.path.isfile(self.file_path):
            log.warn(STRIP(
                """A file named '{} was found but no state file was found at at
                '{}'. Either this file was downloaded to a different
                location, the state file was moved, or the state file
                was deleted.  Parcel refuses to claim the file has
                been successfully downloaded and will restart the
                download.\n""").format(self.file_path, load_path))
            return

        if not os.path.isfile(load_path):
            return

        # If there is a file at load_path, attempt to remove
        # downloaded sections from work_pool
        log.info('Found state file {}, attempting to resume download'.format(
            load_path))

        if not os.path.isfile(self.file_path):
            log.warn(STRIP(
                """State file found at '{}' but no file for {}.
                Restarting entire download.""".format(
                    load_path, self.file_id)))
            return
        try:
            with open(load_path, "rb") as f:
                self.completed = pickle.load(f)
            assert isinstance(self.completed, IntervalTree), \
                "Bad save state: {}".format(load_path)
        except Exception as e:
            self.completed = IntervalTree()
            log.error('Unable to resume file state: {}'.format(str(e)))
        else:
            self.validate_segment_md5sums()
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

    def check_file_exists_and_size(self):
        if self.is_regular_file:
            return (os.path.isfile(self.file_path)
                    and os.path.getsize(self.file_path) == self.size)
        else:
            log.debug('File is not a regular file, refusing to check size.')
            return (os.path.exists(self.file_path))

    def is_complete(self):
        return (self.integrate(self.completed) == self.size and
                self.check_file_exists_and_size())

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
