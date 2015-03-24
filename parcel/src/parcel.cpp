/******************************************************************************
 * parcel.h
 *
 * Header file for parcel.
 *
 *****************************************************************************/

#include "parcel.h"

/******************************************************************************/
EXTERN int server_udt2tcp_start(char *local_host, char *local_port,
                                char *remote_host, char *remote_port)
{
    /*
     *  proxy_start() - starts a UDT proxy server
     *
     *  Starts a proxy server listening on local_host:local_port.
     *  Incomming connections get their own thread and a proxied
     *  connection to remote_host:remote_port.
     */

    addrinfo hints;
    addrinfo* res;
    int mss = MSS;
    int udt_buffer_size = BUFF_SIZE;
    int udp_buffer_size = BUFF_SIZE;
    UDTSOCKET udt_socket;

    /* Setup address information */
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags    = AI_PASSIVE;
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(NULL, local_port, &hints, &res) != 0){
        cerr << "illegal port number or port is busy: "
             << "[" << local_port << "]"
             << endl;
        return 0;
    }

    /* Create the server socket */
    udt_socket = UDT::socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    UDT::setsockopt(udt_socket, 0, UDT_MSS, &mss, sizeof(int));
    UDT::setsockopt(udt_socket, 0, UDT_SNDBUF, &udt_buffer_size, sizeof(int));
    UDT::setsockopt(udt_socket, 0, UDP_SNDBUF, &udp_buffer_size, sizeof(int));

    /* Bind the server socket */
    if (UDT::bind(udt_socket, res->ai_addr, res->ai_addrlen) == UDT::ERROR){
        cerr << "bind: " << UDT::getlasterror().getErrorMessage() << endl;
        return 0;
    }

    /* We no longer need this address information */
    freeaddrinfo(res);

    /* Listen on the port for UDT connections */
    if (UDT::listen(udt_socket, 10) == UDT::ERROR){
        cerr << "listen: " << UDT::getlasterror().getErrorMessage() << endl;
        return 0;
    }

    /* Wait for the next connection */
    UDTSOCKET client_socket;
    sockaddr_storage clientaddr;
    int addrlen = sizeof(clientaddr);
    if ((client_socket = UDT::accept(udt_socket, (sockaddr*)&clientaddr, &addrlen))
        == UDT::INVALID_SOCK){
        cerr << "accept: " << UDT::getlasterror().getErrorMessage() << endl;
        return 0;
    }

    /* Create thread args */
    udt2tcp_args_t *args = (udt2tcp_args_t *) malloc(sizeof(udt2tcp_args_t));
    args->udt_socket  = client_socket;
    args->remote_host = remote_host;
    args->remote_port = remote_port;

    /* Create thread */
    pthread_t client_thread;
    if (pthread_create(&client_thread, NULL, thread_udt2tcp_start, args)){
        cerr << "accept: " << UDT::getlasterror().getErrorMessage() << endl;
        free(args);
    } else {
        pthread_detach(client_thread);
    }

    return 0;
}

EXTERN void *thread_udt2tcp_start(void *_args_)
{
    udt2tcp_args_t *args = (udt2tcp_args_t*) _args_;
    struct addrinfo hints, *local, *peer;
    int tcp_socket;

    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags = AI_PASSIVE;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    if (0 != getaddrinfo(NULL, args->remote_port, &hints, &local)){
        cerr << "incorrect network address.\n" << endl;
        return NULL;
    }

    tcp_socket = socket(local->ai_family, local->ai_socktype, local->ai_protocol);
    freeaddrinfo(local);

    if (0 != getaddrinfo(args->remote_host, args->remote_port, &hints, &peer)){
        cerr << "incorrect server/peer address. "
             << args->remote_host << ":" << args->remote_port
             << endl;
        return NULL;
    }

    /* connect to the server, implicit bind */
    if (connect(tcp_socket, peer->ai_addr, peer->ai_addrlen)){
        perror("connect:");
        return NULL;
    }
    freeaddrinfo(peer);

    return NULL;

}
