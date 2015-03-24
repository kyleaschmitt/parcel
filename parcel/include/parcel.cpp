#include "parcel.h"

using namespace std;

EXTERN int Server::start(char *host, char *port)
{
    // setup socket
    addrinfo hints;
    addrinfo* res;
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags    = AI_PASSIVE;
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    // Setup address information
    if (0 != getaddrinfo(NULL, port, &hints, &res)){
        cerr << "illegal port number or port is busy: [" << port << "]" << endl;
        return 0;
    }

    // Create the server socket
    serv = UDT::socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    UDT::setsockopt(serv, 0, UDT_MSS, &mss, sizeof(int));
    UDT::setsockopt(serv, 0, UDT_SNDBUF, &udt_buff, sizeof(int));
    UDT::setsockopt(serv, 0, UDP_SNDBUF, &udp_buff, sizeof(int));

    // Bind the server socket
    if (UDT::ERROR == UDT::bind(serv, res->ai_addr, res->ai_addrlen)){
        cerr << "bind: " << UDT::getlasterror().getErrorMessage() << endl;
        return 0;
    }
    freeaddrinfo(res);

    // Listen on the port
    if (UDT::ERROR == UDT::listen(serv, 10)){
        cerr << "listen: " << UDT::getlasterror().getErrorMessage() << endl;
        return 0;
    }

    // Incoming connections should be recieved by calling
    // next_client() repeatedly
    return 0;
}
