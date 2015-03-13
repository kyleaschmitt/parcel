import parcel
import argparse
import logging

logging.root.setLevel(logging.INFO)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--data-server-url', required=True, type=str,
                        help='location of data server')
    parser.add_argument('-p', '--port', default=9000, type=int,
                        help='parcel server port')
    parser.add_argument('-i', '--host', default='localhost', type=str,
                        help='parcel server port')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='verbose logging')
    args = parser.parse_args()

    if args.verbose:
        logging.root.setLevel(logging.DEBUG)

    sthread_args = {
        'data_server_url': args.data_server_url,
    }

    server = parcel.Server()
    server.start(host=args.host, port=args.port, sthread_args=sthread_args)
