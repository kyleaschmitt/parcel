## Synopsis

A high performance HTTP download client that leverages the speed of UDP without sacrificing reliability.

Parcel is written on top of the UDT protocol and bound to a python interface.  Parcel's software is comprised of a *parcel-server* and a *parcel* client.

## Usage

#### Using UDT

The client can be run in conjunction with a parcel server, or without one.  The advantage of running the client with the server (option `udt`) is the UDT proxy layer.  This prevents performance degredation of Wide Area Networks.

The server is given a REST endpoint with access to data.  The client connects to the server via UDT and the data is translated to a local TCP connection. Any TCP response is then proxied back using UDT.

#### Using TCP

Using the `http` option is alternative to running the client against a server with the `udt` option.  It can be run directly against a REST api without any additional server. Using this method, you are likely to see decreased performance over high latency networks.

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

## Installation

To install both the server and the client, simply run (preferrably in a python virtual environment):
```
❯ make
❯ sudo make install
❯ python setup.py install
```

## Tests

To run the tests:

```
❯ pip install pytest
❯ py.test
```
