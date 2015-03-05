import unittest
import parcel


class TestParcel(unittest.TestCase):

    def setUp(self):
        pass

    def test_library_import(self):
        print parcel.Server()
