## Synopsis

A high performance HTTP download client that leverages the speed of UDP without sacrificing reliability.

Parcel is written on top of the UDT protocol and bound to a python interface.  Parcel's software is comprised of a *parcel-server* and a *parcel* client.

## Download and run

For the latest parcel app, visit the [downloads](https://github.com/LabAdvComp/parcel/releases) here.  These binaries are self-contained executables and will not install the app globally on your system.

## Installing from source

You can also install from source with:
```
❯ pip install -e 'git+https://github.com/LabAdvComp/parcel#egg=parcel'
```

## Usage

#### Using: TCP

This is the default option and can be run directly against a REST api without any additional server. Using this method, you are likely to see decreased performance over high latency networks.

#### Using: UDT

The client can be run in conjunction with a parcel server, or without one.  The advantage of running the client with the server (option `udt`) is the UDT proxy layer.  This prevents performance degredation of Wide Area Networks.

The server is given a REST endpoint with access to data.  The client connects to the server via UDT and the data is translated to a local TCP connection. Any TCP response is then proxied back using UDT.

Note: The UDT option is not currently bundled with executable binaries, you must install from source.

## Example Usage
To use the client interactively
```
❯ parcel
```
OR
```
❯ parcel -t token_file file_id1 file_id2
```
OR
```
❯ parcel -u -t token_file file_id1 file_id2
```

## Motivation

TCP is the most widely used reliable network transport protocol. However, over high performance, wide area networks, TCP has been show to reach a bottleneck before UDP.

UDT (UDP Based Data transfer) is a reliable application level protocol for transferring bulk data over wide area networks.

## Dependencies

- [Python 2.7+](http://python.org/)
- [Python pip](https://pypi.python.org/pypi/pip)

## Tests

To run the tests:

```
❯ pip install pytest
❯ py.test
```
