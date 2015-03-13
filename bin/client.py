import argparse
import parcel

from parcel import manifest

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

    args = parser.parse_args()

    client = parcel.Client(args.token, port=args.port)

    for entry in args.manifest:
        # TODO client to interpret other manifest fields
        client.download(entry['uuid'])

    for file_id in args.file_ids:
        client.download(file_id)
