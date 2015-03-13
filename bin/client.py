import argparse
import parcel
import logging

from parcel import manifest


logging.root.setLevel(logging.INFO)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('file_ids', metavar='file_id', type=str, nargs='*',
                        help='uuids to download')
    parser.add_argument('-t', '--token', default='', type=str,
                        help='authentication token')
    # NOTE should we allow this in combination w/ other file_ids?
    parser.add_argument('-m', '--manifest',
                        type=manifest.argparse_type,
                        default=list(),
                        help='GDC Download anifest file.')
    parser.add_argument('-p', '--port', default=9000, type=str,
                        help='parcel server port')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='verbose logging')

    args = parser.parse_args()

    # Set verbosty
    if args.verbose:
        logging.root.setLevel(logging.DEBUG)

    # Create client
    client = parcel.Client(args.token, port=args.port)

    # Send manifest files
    for entry in args.manifest:
        # TODO client to interpret other manifest fields
        client.download(entry['uuid'])

    # Send argument files
    for file_id in args.file_ids:
        client.download(file_id)
