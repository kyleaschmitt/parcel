import argparse
import parcel

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('file_ids', metavar='file_id', type=str, nargs='*',
                        help='uuids to download')
    parser.add_argument('-t', '--token', default='', type=str,
                        help='authentication token')
    # NOTE should we allow this in combination w/ other file_ids?
    parser.add_argument('-m', '--manifest', type=argparse.FileType('r'),
                        help='GDC Download anifest file.')

    args = parser.parse_args()

    client = parcel.Client(args.token)

    manifest = parcel.manifest.parse(args.manifest) if args.manifest else []
    for entry in manifest:
        # TODO client to interpret other manifest fields
        client.download(entry['uuid'])

    for file_id in args.file_ids:
        client.download(file_id)
