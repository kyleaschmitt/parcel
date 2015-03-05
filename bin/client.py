import argparse
import parcel

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('file_ids', metavar='file_id', type=str, nargs='+',
                        help='uuids to download')
    parser.add_argument('-t', '--token', type=str, help='authentication token')

    args = parser.parse_args()
    client = parcel.Client(args.token)
    for file_id in args.file_ids:
        client.download(file_id)
