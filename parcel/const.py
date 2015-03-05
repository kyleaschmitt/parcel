from ctypes import cdll, create_string_buffer
lib = cdll.LoadLibrary('lparcel.so')
import logging
import atexit

log = logging.getLogger('parcel')




class Server(object):

    def __init__(self):
        """
        Creates a new udpipeClient instance from shared object library
        """

        self.server = lib.new_server()
        atexit.register(self.close)

    def start(self, host='localhost', port=9000):
        print('Starting server at {}:{}'.format(host, port))
        return lib.server_start(self.server, str(host), str(port))

    def close(self):
        lib.server_close(self.server)

    def listen(self):
        while True:
            yield ServerThread(lib.server_next_client(self.server))


class ParcelThread(object):

    def __init__(self, instance, read_func, send_func, close_func):
        """
        Creates a new udpipeClient instance from shared object library
        """

        atexit.register(self.close)
        self.instance = instance
        self.read_func = read_func
        self.send_func = send_func
        self.close_func = close_func
        self.buff_len = 64000000
        self.buff = create_string_buffer(self.buff_len)

    def read(self):
        while True:
            print 'Reading'
            rs = self.read_func(self.instance, self.buff, self.buff_len)
            if rs < 0:
                raise StopIteration()
            print 'Read {} bytes'.format(rs)
            yield self.buff[:rs]

    def send(self, data):
        self.send_func(self.instance, data, len(data))

    def send_control(self, cntl):


    def close(self):
        self.close_func(self.instance)


class ServerThread(ParcelThread):

    def __init__(self, instance):
        super(ServerThread, self).__init__(
            instance=instance,
            read_func=lib.sthread_read,
            send_func=lib.sthread_send,
            close_func=lib.sthread_close,
        )


class Client(ParcelThread):

    def __init__(self):
        super(Client, self).__init__(
            instance=lib.new_client(),
            read_func=lib.client_read,
            send_func=lib.client_send,
            close_func=lib.client_close,
        )

    def start(self, host='localhost', port=9000):
        print('Connecting to server at {}:{}'.format(host, port))
        return lib.client_start(self.instance, str(host), str(port))
