import argparse
import parcel

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--token', type=str, help='authentication token')
    args = parser.parse_args()
    client = parcel.Client(args.token)
