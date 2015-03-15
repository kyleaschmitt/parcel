## Synopsis

Parcel is a high speed download client that leverages the speed of UDP without sacrificing reliability.  It is written on top of the UDT protocol and bound to a python interface.  Parcel's software is comprised of a *parcel-server* and a *parcel* client.  

The server is given a local REST endpoint with access to data.  The client connects to the server, providing any authentication information to proxy through to the REST endpoint.  The server then proxies the data back with a parallel HTTP/S buffer from the REST endpoint over UDT.

## Example Usage

```
ubuntu$ parcel --host parcel.server.host 10G -t token_file
[2015-03-15 11:41:33,271][  client][   INFO] Connecting to server at parcel.server.host:9000
[2015-03-15 11:41:33,274][  client][   INFO] Requesting 4 encryption threads
[2015-03-15 11:41:33,275][  client][   INFO] Waiting for response...
[2015-03-15 11:41:33,276][  client][   INFO] Encryption threads granted. Server will provide up to 4 threads.
[2015-03-15 11:41:33,278][  client][   INFO] Found file id: 10G
[2015-03-15 11:41:33,285][  client][   INFO] ----------------------------------------
[2015-03-15 11:41:33,285][  client][   INFO] Starting download   : 10G
[2015-03-15 11:41:33,285][  client][   INFO] ----------------------------------------
[2015-03-15 11:41:33,285][  client][   INFO] File name           : None
[2015-03-15 11:41:33,285][  client][   INFO] Download size       : 10737418240
[2015-03-15 11:41:33,286][  client][   INFO] Downloading file to : /home/ubuntu/10G
```

## Motivation

TCP is the most widely used reliable network transport protocol. However, over high performance, wide area networks, TCP has been show to reach a bottleneck before UDP. 

UDT (UDP Based Data transfer) is a reliable application level protocol for transferring bulk data over wide area networks. Parcel

## Dependencies

- OpenSSL (libssl and libcrypto)
- [Python 2.7+](http://python.org/)
- [Postgresql 9.4](http://www.postgresql.org/download/)

## Installation

To install both the server and the client, simply run (preferrably in a python virtual environment):
❯ cd parcel
❯ ./install parcel

## Tests

Are currently being developed.
