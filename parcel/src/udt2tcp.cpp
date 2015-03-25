/******************************************************************************
 * parcel.cpp
 *
 * Parcel udt proxy server
 *
 *****************************************************************************/
#include "parcel.h"


EXTERN int udt2tcp_start(char *local_host, char *local_port,
                         char *remote_host, char *remote_port)
{
    /*
     *  udt2tcp_start() - starts a UDT proxy server
     *
     *  Starts a proxy server listening on local_host:local_port.
     *  Incomming connections get their own thread and a proxied
     *  connection to remote_host:remote_port.
     */

    log("Proxy binding to local UDT socket [%s:%s] to remote TCP [%s:%s]",
        local_host, local_port, remote_host, remote_port);

    addrinfo hints;
    addrinfo* res;
    int mss = MSS;
    int udt_buffer_size = BUFF_SIZE;
    int udp_buffer_size = BUFF_SIZE;
    UDTSOCKET udt_socket;

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
    debug("Proxy bound to UDT socket [%s:%s]", local_host, local_port);

    /* We no longer need this address information */
    freeaddrinfo(res);

    /* Listen on the port for UDT connections */
    debug("Calling UDT socket listen");
    if (UDT::listen(udt_socket, 10) == UDT::ERROR){
        cerr << "listen: " << UDT::getlasterror().getErrorMessage() << endl;
        return 0;
    }

    /*******************************************************************
     * Accept clients
     ******************************************************************/

    while (1){
        /* Wait for the next connection */
        UDTSOCKET client_socket;
        sockaddr_storage clientaddr;
        int addrlen = sizeof(clientaddr);

        /* Wait for the next connection */
        debug("Accepting incoming UDT connections");
        if ((client_socket = UDT::accept(udt_socket, (sockaddr*)&clientaddr, &addrlen))
            == UDT::INVALID_SOCK){
            cerr << "accept: " << UDT::getlasterror().getErrorMessage() << endl;
            return 0;
        }
        debug("New UDT connection");

        /* Create transcriber thread args */
        transcriber_args_t *transcriber_args = (transcriber_args_t *) malloc(sizeof(transcriber_args_t));
        transcriber_args->tcp_socket  = 0;  // will be set by thread_udt2tcp
        transcriber_args->udt_socket  = client_socket;
        transcriber_args->remote_host = remote_host;
        transcriber_args->remote_port = remote_port;

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

    return 0;
}

int connect_remote_tcp(udt2tcp_args_t *args)
{
    /*
     *  connect_remote_tct() - Creates client connection to tcp server
     *
     *  Connects a TCP socket to a remote tcp server.
     */

    struct addrinfo hints, *local, *peer;
    int tcp_socket;

    /* Create address information */
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags = AI_PASSIVE;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (0 != getaddrinfo(NULL, args->remote_port, &hints, &local)){
        perror("incorrect network address");
        return -1;
    }

    /* Create the new socket */
    tcp_socket = socket(local->ai_family, local->ai_socktype, local->ai_protocol);
    freeaddrinfo(local);
    if (0 != getaddrinfo(args->remote_host, args->remote_port, &hints, &peer)){
        cerr << "incorrect server/peer address. "
             << args->remote_host << ":" << args->remote_port
             << endl;
        return -1;
    }

    /* Connect to the remote tcp server */
    if (connect(tcp_socket, peer->ai_addr, peer->ai_addrlen)){
        perror("connect:");
        return -1;
    }
    freeaddrinfo(peer);
    return tcp_socket;
}

void *thread_udt2tcp(void *_args_)
{
    /*
     *  thread_udt2tcp() -
     *
     */
    udt2tcp_args_t *args = (udt2tcp_args_t*) _args_;

    /*******************************************************************
     * Setup proxy procedure
     ******************************************************************/

    /*
     * I've made the design choice that the udt2tcp thread is not
     * responsible for the udt socket, because it is reading from it,
     * not writing.  Therefore, we will wait for an external entity to
     * set args->udt_socket to be a valid descriptor (it may already
     * be valid as set by a _start() method).
     */
    debug("Waiting on UDT socket ready");
    while (!args->udt_socket){
        pthread_yield();
    }
    debug("UDT socket ready: %d", args->udt_socket);

    /*
     * Similarly I've made the design choice that the udt2tcp thread
     * IS responsible for the tcp socket, because it is writing to it,
     * not reading.  Therefore, we will attempt to connect to a remote
     * server via tcp. However, if there is already an existing tcp
     * connection, then by golly, someone wants us to use it (that
     * someone is me or you?).
     */
    if (!args->tcp_socket){
        if ((args->tcp_socket = connect_remote_tcp(args)) < 0){
            free(args);
            return NULL;
        }
    }

    /* Create udt2tcp pipe, read from 0, write to 1 */
    int pipefd[2];
    if (pipe(pipefd) == -1) {
        perror("pipe");
        free(args);
        return NULL;
    }

    /*******************************************************************
     * Begin proxy procedure
     ******************************************************************/

    /* Create UDT to pipe thread */
    pthread_t udt2pipe_thread;
    udt_pipe_args_t *udt2pipe_args = (udt_pipe_args_t*)malloc(sizeof(udt_pipe_args_t));
    udt2pipe_args->udt_socket = args->udt_socket;
    udt2pipe_args->pipe = pipefd[1];
    debug("Creating udt2pipe thread");
    if (pthread_create(&udt2pipe_thread, NULL, udt2pipe, udt2pipe_args)){
        perror("unable to create udt2pipe thread");
        free(args);
        return NULL;
    }

    /* Create pipe to TCP thread */
    pthread_t pipe2tcp_thread;
    tcp_pipe_args_t *pipe2tcp_args = (tcp_pipe_args_t*)malloc(sizeof(tcp_pipe_args_t));
    pipe2tcp_args->tcp_socket = args->tcp_socket;
    pipe2tcp_args->pipe = pipefd[0];
    debug("Creating pipe2tcp thread");
    if (pthread_create(&pipe2tcp_thread, NULL, pipe2tcp, pipe2tcp_args)){
        perror("unable to create pipe2udt thread");
        free(args);
        return NULL;
    }

    /* Join transcriber threads */
    void *ret;
    pthread_join(udt2pipe_thread, &ret);
    pthread_join(pipe2tcp_thread, &ret);

    return NULL;
}
