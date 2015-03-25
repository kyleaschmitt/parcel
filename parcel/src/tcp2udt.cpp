/******************************************************************************
 *
 * FILE    : tcp2udt.cpp
 * AUTHOR  : Joshua Miller
 *           jshuasmiller@gmail.com              _
 * PROJECT : parcel                             | |
 *                      _ __   __ _ _ __ ___ ___| |
 *                     | '_ \ / _` | '__/ __/ _ \ |
 *                     | |_) | (_| | | | (_|  __/ |
 *                     | .__/ \__,_|_|  \___\___|_|
 *                     | |
 *                     |_|
 *
 * DESCRIPTION : This file contains functions for creating a TCP
 *               server that accpts incomming connections, creates a
 *               UDT connection to remote server, and proxies the
 *               traffic through.
 *
 * LICENSE : Licensed under the Apache License, Version 2.0 (the
 *           "License"); you may not use this file except in
 *           compliance with the License.  You may obtain a copy of
 *           the License at
 *
 *               http://www.apache.org/licenses/LICENSE-2.0
 *
 *           Unless required by applicable law or agreed to in
 *           writing, software distributed under the License is
 *           distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
 *           CONDITIONS OF ANY KIND, either express or implied.  See
 *           the License for the specific language governing
 *           permissions and limitations under the License.)
 *
 ******************************************************************************/

#include "parcel.h"

int TCP_SERVER_SOCKET = 0;


EXTERN int tcp2udt_start(char *local_host, char *local_port,
                         char *remote_host, char *remote_port)
{
    /*
     *  tcp2udt_start() - starts a TCP-to-UDT proxy thread
     *
     *  Starts a proxy server listening on local_host:local_port.
     *  Incomming connections get their own thread and a proxied
     *  connection to remote_host:remote_port.
     */
    log("Proxy binding to local TCP socket [%s:%s] to remote UDT [%s:%s]",
        local_host, local_port, remote_host, remote_port);

    addrinfo hints;
    addrinfo* res;
    int tcp_socket;

    /*******************************************************************
     * Establish server socket
     ******************************************************************/

    /* Setup address information */
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags    = AI_PASSIVE;
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(NULL, local_port, &hints, &res) != 0){
        cerr << "illegal port number or port is busy: "
             << "[" << local_port << "]"
             << endl;
        return -1;
    }

    /* Create the server socket */
    tcp_socket = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (tcp_socket < 0){
        perror("Unable to create TCP socket");
        return -1;
    }

    /* Bind the server socket */
    log("Proxy binding to TCP socket [%s:%s]", local_host, local_port);
    if (bind(tcp_socket, res->ai_addr, res->ai_addrlen)){
        perror("Unable to bind TCP socket");
        return -1;
    }
    log("Proxy bound to local TCP socket [%s:%s] to remote UDT [%s:%s]",
        local_host, local_port, remote_host, remote_port);

    /* We no longer need this address information */
    freeaddrinfo(res);

    /* Listen on the port for TCP connections */
    debug("Calling socket listen");
    if (listen(tcp_socket, 10)){
        perror("Unable to call TCP socket listen");
        return -1;
    }

    debug("Creating pipe2tcp server thread");
    pthread_t tcp2udt_server_thread;
    server_args_t *args = (server_args_t*) malloc(sizeof(server_args_t));
    args->remote_host = strdup(remote_host);
    args->remote_port = strdup(remote_port);
    args->tcp_socket  = tcp_socket;
    if (pthread_create(&tcp2udt_server_thread, NULL, tcp2udt_accept_clients, args)){
        perror("unable to create tcp2udt server thread");
        free(args);
        return -1;
    }

    return 0;
}

EXTERN void *tcp2udt_accept_clients(void *_args_)
{
    /*
     *  udt2tcp_accept_clients() - Accepts incoming UDT clients
     *
     */
    server_args_t *args = (server_args_t*) _args_;
    while (1) {

        int client_socket;
        sockaddr_storage clientaddr;
        socklen_t addrlen = sizeof(clientaddr);

        /* Wait for the next connection */
        debug("Accepting incoming TCP connections");
        client_socket = accept(args->tcp_socket, (sockaddr*)&clientaddr, &addrlen);
        if (client_socket < 0){
            perror("Socket accept failed");
            return 0;
        }
        debug("New TCP connection");

        /*******************************************************************
         * Create proxy threads
         ******************************************************************/

        /* Create transcriber thread args */
        transcriber_args_t *transcriber_args = (transcriber_args_t *) malloc(sizeof(transcriber_args_t));
        transcriber_args->udt_socket  = 0;  // will be set by thread_tcp2udt
        transcriber_args->tcp_socket  = client_socket;
        transcriber_args->remote_host = args->remote_host;
        transcriber_args->remote_port = args->remote_port;

        /* Create tcp2udt thread */
        pthread_t tcp_thread;
        if (pthread_create(&tcp_thread, NULL, thread_tcp2udt, transcriber_args)){
            perror("Unable to TCP thread");
            free(transcriber_args);
            return 0;
        } else {
            pthread_detach(tcp_thread);
        }

        /* Create udt2tcp thread */
        pthread_t udt_thread;
        if (pthread_create(&udt_thread, NULL, thread_udt2tcp, transcriber_args)){
            perror("Unable to TCP thread");
            free(transcriber_args);
            return 0;
        } else {
            pthread_detach(udt_thread);
        }

    }
    return NULL;
}

int connect_remote_udt(transcriber_args_t *args)
{
    /*
     *  connect_remote_udt() - Creates client connection to UDT server
     *
     */
    debug("Connecting to remote UDT at [%s:%s]",
          args->remote_host, args->remote_port);

    UDTSOCKET udt_socket;
    int mss = MSS;
    int udt_buff = BUFF_SIZE;
    int udp_buff = BUFF_SIZE;

    /* Create address information */
    struct addrinfo hints, *local, *peer;
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags = AI_PASSIVE;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (0 != getaddrinfo(NULL, args->remote_port, &hints, &local)){
        cerr << "incorrect network address.\n" << endl;
        return -1;
    }

    /* Create UDT socket */
    udt_socket = UDT::socket(local->ai_family, local->ai_socktype, local->ai_protocol);
    freeaddrinfo(local);

    /* Set UDT options */
    UDT::setsockopt(udt_socket, 0, UDT_MSS, &mss, sizeof(int));
    UDT::setsockopt(udt_socket, 0, UDT_SNDBUF, &udt_buff, sizeof(int));
    UDT::setsockopt(udt_socket, 0, UDP_SNDBUF, &udp_buff, sizeof(int));

    /* Get address information */
    if (0 != getaddrinfo(args->remote_host, args->remote_port, &hints, &peer)){
        cerr << "incorrect server/peer address. "
             << args->remote_host << ":" << args->remote_port << endl;
        freeaddrinfo(peer);
        return -1;
    }

    /* Connect to the server */
    debug("Connecting to remote UDT server");
    if (UDT::ERROR == UDT::connect(udt_socket, peer->ai_addr, peer->ai_addrlen)){
        cerr << "connect: " << UDT::getlasterror().getErrorMessage() << endl;
        freeaddrinfo(peer);
        return -1;
    }

    freeaddrinfo(peer);
    return udt_socket;
}


void *thread_tcp2udt(void *_args_)
{
    /*
     *  thread_tcp2udt() -
     *
     */
    transcriber_args_t *args = (transcriber_args_t*) _args_;

    /*******************************************************************
     * Setup proxy procedure
     ******************************************************************/

    /*
     * I've made the design choice that the tcp2udt thread is not
     * responsible for the tcp socket, because it is reading from it,
     * not writing.  Therefore, we will wait for an external entity to
     * set args->tcp_socket to be a valid descriptor (it may already
     * be valid as set by a _start() method).
     */
    debug("Waiting on TCP socket ready");
    while (!args->tcp_socket){
        // TODO: Add semaphore on socket ready, pthread_yield is a
        // lazy solution for now
        pthread_yield();
    }
    debug("TCP socket ready: %d", args->tcp_socket);

    /*
     * Similarly I've made the design choice that the tcp2udt thread
     * IS responsible for the udt socket, because it is writing to it,
     * not reading.  Therefore, we will attempt to connect to a remote
     * server via udt. However, if there is already an existing udt
     * connection, then by golly, someone wants us to use it (that
     * someone is me or you?).
     */
    if (!args->udt_socket){
        if ((args->udt_socket = connect_remote_udt(args)) <= 0){
            close(args->udt_socket);
            free(args);
            return NULL;
        }
    }

    /*******************************************************************
     * Begin proxy procedure
     ******************************************************************/

    /* Create pipe, read from 0, write to 1 */
    int pipefd[2];
    if (pipe(pipefd) == -1) {
        perror("pipe");
        free(args);
        return NULL;
    }

    /* Create UDT to pipe thread */
    pthread_t tcp2pipe_thread;
    tcp_pipe_args_t *tcp2pipe_args = (tcp_pipe_args_t*)malloc(sizeof(tcp_pipe_args_t));
    tcp2pipe_args->tcp_socket = args->tcp_socket;
    tcp2pipe_args->pipe = pipefd[1];
    debug("Creating tcp2pipe thread");
    if (pthread_create(&tcp2pipe_thread, NULL, tcp2pipe, tcp2pipe_args)){
        perror("unable to create tcp2pipe thread");
        free(args);
        return NULL;
    }

    /* Create pipe to TCP args */
    udt_pipe_args_t *pipe2udt_args = (udt_pipe_args_t*)malloc(sizeof(udt_pipe_args_t));
    pipe2udt_args->udt_socket = args->udt_socket;
    pipe2udt_args->pipe = pipefd[0];
    debug("Calling pipe2udt");
    pipe2udt(pipe2udt_args);  // There is no reason not to block on this now

    void *ret;
    pthread_join(tcp2pipe_thread, &ret);

    return NULL;
}
