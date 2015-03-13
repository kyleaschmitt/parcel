import parcel
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--data-server-url', required=True, type=str,
                        help='location of data server')
    parser.add_argument('-p', '--port', default=9000, type=int,
                        help='parcel server port')
    parser.add_argument('-i', '--host', default='localhost', type=str,
                        help='parcel server port')
    args = parser.parse_args()

    sthread_args = {
        'data_server_url': args.data_server_url,
    }

    server = parcel.Server()
    server.start(host=args.host, port=args.port, sthread_args=sthread_args)
