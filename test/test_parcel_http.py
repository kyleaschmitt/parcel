import unittest
from parcel import mock_server
from tempfile import NamedTemporaryFile
import random
from multiprocessing import Process
from subprocess import check_call


class TestParcelHTTP(unittest.TestCase):

    def setUp(self):
        self.files = [NamedTemporaryFile() for i in range(10)]
        for f in self.files:
            f.write(str(range(random.randint(100, 300))))
            f.flush()
        self.server = Process(
            target=mock_server.app.run,
            kwargs=dict(debug=True, threaded=True))
        self.server.start()
        self.file_ids = [f.name.split('/')[-1] for f in self.files]

    def tearDown(self):
        self.server.terminate()

    def test_whole_file(self):
        # print self.file_ids
        # import time
        # time.sleep(30)
        for file_id in self.file_ids:
            print file_id
            check_call(
                ['parcel', 'http', '-v', 'http://localhost:5000', file_id])
