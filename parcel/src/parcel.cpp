#ifndef WIN32
#include <unistd.h>
#include <cstdlib>
#include <cstring>
#include <netdb.h>
#else
#include <winsock2.h>
#include <ws2tcpip.h>
#include <wspiapi.h>
#endif
#include <iostream>
#include <assert.h>
#include <udt.h>
#include "crypto.h"

#define BUFF_SIZE 67108864
#define MSS 8400
#define EXTERN extern "C"

using namespace std;

typedef struct monitor_args {
    int live;
    int64_t downloaded;
    int64_t file_size;
    UDTSOCKET *s;
} monitor_args;

void* recvdata(void*);
void* monitor(void* margs);
EXTERN int send_data_no_encryption(UDTSOCKET socket, char *data, int size);
EXTERN int read_data_no_encryption(UDTSOCKET socket, char *data, int size);
EXTERN int read_size_no_encryption(UDTSOCKET socket, char *buff, int len);
EXTERN int read_data(ThreadedEncryption *decryptor, UDTSOCKET socket,
                     char *buff, int len);
EXTERN int read_size(ThreadedEncryption *decryptor, UDTSOCKET socket,
                     char *buff, int len);

class ServerThread
{
public:
    UDTSOCKET recver;
    char* data;
    char clienthost[NI_MAXHOST];
    char clientport[NI_MAXSERV];
    int udt_buff;

    ServerThread(UDTSOCKET *socket, char* host, char* port);
    int close();
};

class Server
{
public:
    int blast;
    int blast_rate;
    int udt_buff;
    int udp_buff;
    int mss;
    UDTSOCKET serv;

    Server();
    int close();
    ServerThread *next_client();
    int start(char *host, char *port);
    int set_buffer_size(int size);
};


class Client
{
public:
    int blast;
    int blast_rate;
    int udt_buff;
    int udp_buff;
    int mss;
    UDTSOCKET client;
    monitor_args margs;

    Client();
    int close();
    int start(char *host, char *port);
};


Server::Server()
{
    blast = 0;
    blast_rate = 0;
    udt_buff = BUFF_SIZE;
    udp_buff = BUFF_SIZE;
    mss = MSS;
}

int Server::start(char *host, char *port)
{
    // setup socket
    addrinfo hints;
    addrinfo* res;
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags = AI_PASSIVE;
    hints.ai_family = AF_INET;
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

int Server::close()
{
    UDT::close(serv);
    return 0;
}

ServerThread *Server::next_client(){

    UDTSOCKET recver;
    sockaddr_storage clientaddr;
    int addrlen = sizeof(clientaddr);


    // Wait for the next connection
    recver = UDT::accept(serv, (sockaddr*)&clientaddr, &addrlen);
    if (UDT::INVALID_SOCK == recver){
        cerr << "accept: " << UDT::getlasterror().getErrorMessage() << endl;
        return 0;
    }

    // Get the client information
    char clienthost[NI_MAXHOST];
    char clientservice[NI_MAXSERV];
    getnameinfo((sockaddr *)&clientaddr,
                addrlen,
                clienthost,
                sizeof(clienthost),
                clientservice,
                sizeof(clientservice),
                NI_NUMERICHOST|NI_NUMERICSERV);

    // Return a ServerThread object that belongs to the new client
    return new ServerThread(new UDTSOCKET(recver), clienthost, clientservice);
}

Client::Client()
{
    blast = 0;
    blast_rate = 0;
    udt_buff = BUFF_SIZE;
    udp_buff = BUFF_SIZE;
    mss = MSS;
}

int Client::start(char *host, char *port)
{
    struct addrinfo hints, *local, *peer;
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags = AI_PASSIVE;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    if (0 != getaddrinfo(NULL, port, &hints, &local)){
        cerr << "incorrect network address.\n" << endl;
        return -1;
    }

    client = UDT::socket(local->ai_family, local->ai_socktype,
                         local->ai_protocol);
    freeaddrinfo(local);

    UDT::setsockopt(client, 0, UDT_MSS, &mss, sizeof(int));
    UDT::setsockopt(client, 0, UDT_SNDBUF, &udt_buff, sizeof(int));
    UDT::setsockopt(client, 0, UDP_SNDBUF, &udp_buff, sizeof(int));

    if (0 != getaddrinfo(host, port, &hints, &peer)){
        cerr << "incorrect server/peer address. " << host << ":" << port
             << endl;
        return -1;
    }

    // connect to the server, implicit bind
    if (UDT::ERROR == UDT::connect(client, peer->ai_addr, peer->ai_addrlen)){
        cerr << "connect: " << UDT::getlasterror().getErrorMessage() << endl;
        return -1;
    }
    freeaddrinfo(peer);
    return 0;
}


int Client::close()
{
    UDT::close(client);
    return 0;
}


ServerThread::ServerThread(UDTSOCKET *usocket, char *host, char *port){
    memcpy(clienthost, host, NI_MAXHOST);
    memcpy(clientport, port, NI_MAXSERV);
    recver = *(UDTSOCKET*)usocket;
    delete (UDTSOCKET*)usocket;
}

int ServerThread::close(){
    return UDT::close(recver);
}

/***********************************************************************
 *                           Data transfer
 ***********************************************************************/

EXTERN int send_data_no_encryption(UDTSOCKET socket, char *data, int size)
{
    int ss = 0;
    int ssize = 0;
    while (ssize < size) {
        // Send as much data as we can
        ss = UDT::send(socket, data + ssize, size - ssize, 0);
        // Check for errors
        if (UDT::ERROR == ss){
            cerr << "send:" << UDT::getlasterror().getErrorMessage() << endl;
            break;
        }
        // Increment the amount sent before repeating
        ssize += ss;
    }
    return ssize;
}

EXTERN int read_data_no_encryption(UDTSOCKET socket, char *buff, int len)
{
    assert(len >= 0);
    int rs = UDT::recv(socket, buff, len, 0);
    if (UDT::ERROR == rs) {
        if (UDT::getlasterror().getErrorCode() != 2001)
            cerr << "recv:" << UDT::getlasterror().getErrorMessage() << endl;
        return -1;
    }
    return rs;
}

EXTERN int read_size_no_encryption(UDTSOCKET socket, char *buff, int len)
{
    assert(len >= 0);
    int rs = 0;
    int ret = 0;
    while (rs < len){
        if ((ret = read_data_no_encryption(socket, buff+rs, len - rs)) < 0){
            return ret;
        }
        rs += ret;
    }
    return rs;
}

EXTERN int read_data(ThreadedEncryption *decryptor, UDTSOCKET socket,
                     char *buff, int len)
{
    int rs = read_data_no_encryption(socket, buff, len);
    decryptor->map_threaded(buff, buff, rs);
    return rs;
}

EXTERN int read_size(ThreadedEncryption *decryptor, UDTSOCKET socket,
                     char *buff, int len)
{
    int rs = read_size_no_encryption(socket, buff, len);
    decryptor->map_threaded(buff, buff, rs);
    return rs;
}

EXTERN int send_data(ThreadedEncryption *encryptor, UDTSOCKET socket,
                     char *buff, int len)
{
    encryptor->map_threaded(buff, buff, len);
    int ss = send_data_no_encryption(socket, buff, len);
    return ss;
}


/***********************************************************************
 *                        Encryption functions
 ***********************************************************************/

EXTERN ThreadedEncryption *encryption_init(char *key, int n_threads)
{
    return new ThreadedEncryption(EVP_ENCRYPT, (unsigned char*)key, n_threads);
}

EXTERN ThreadedEncryption *decryption_init(char *key, int n_threads)
{
    return new ThreadedEncryption(EVP_DECRYPT, (unsigned char*)key, n_threads);
}

/***********************************************************************
 *                Wrappers for CTypes Python bindings
 ***********************************************************************/

EXTERN Client* new_client(){
    return new Client();
}


EXTERN int client_start(Client *client, char *host, char *port){
    return client->start(host, port);
}

EXTERN int client_close(Client *client){
    client->close();
    delete client;
    return 0;
}

EXTERN Server* new_server(){
    return new Server();
}

EXTERN ServerThread* server_next_client(Server *server){
    return server->next_client();
}

EXTERN int server_set_buffer_size(Server *server, int size){
    server->udt_buff = size;
    return 0;
}

EXTERN int server_start(Server *server, char *host, char *port){
    return server->start(host, port);
}

EXTERN int server_close(Server *server){
    server->close();
    delete server;
    return 0;
}

EXTERN int sthread_close(Server *sthread){
    sthread->close();
    delete sthread;
    return 0;
}

EXTERN char* sthread_get_clienthost(ServerThread *sthread){
    return sthread->clienthost;
}

EXTERN char* sthread_get_clientport(ServerThread *sthread){
    return sthread->clientport;
}

EXTERN UDTSOCKET sthread_get_socket(ServerThread *sthread){
    return sthread->recver;
}

EXTERN UDTSOCKET client_get_socket(Client *client){
    return client->client;
}


EXTERN long long client_recv_file(ThreadedEncryption *decryptor, Client *client,
                                  char *path, int64_t size,
                                  int64_t block_size, int print_stats)
{

    char *buffer = new char[block_size];
    fstream ofs(path, ios::out | ios::binary | ios::trunc);
    int64_t total_read = 0;
    client->margs.downloaded = 0;
    client->margs.live = 1;

    while (total_read < size){
        int64_t this_size = min(size-total_read, block_size);
        int rs = read_size(decryptor, client->client, buffer, this_size);
        if (rs < 0){
            cerr << "Unable to write to file: " << path << endl;
            return rs;
        }
        if (!ofs.write(buffer, rs)){
            cerr << "Unable to write to file: " << path << endl;
            return -1;
        }
        total_read += rs;
        if (print_stats){
            client->margs.downloaded = total_read;
        }
    }

    ofs.close();
    delete buffer;
    client->margs.live = 0;

    return total_read;
}

void* monitor(void* _arg)
{
    monitor_args *margs = (monitor_args*)_arg;
    UDT::TRACEINFO perf;
    while (margs->live) {
        sleep(1);
        if (UDT::ERROR == UDT::perfmon(*margs->s, &perf)) {
            cout << "perfmon: " << UDT::getlasterror().getErrorMessage() << endl;
            break;
        }
        fprintf(stderr, "%c[2K\t\t", 27);  // Clear line
        cerr.width(16);
        cerr.precision(4);
        cerr.setf( std::ios::fixed, std:: ios::floatfield );
        cerr <<  "Gbps: " << perf.mbpsRecvRate/1e3;
        cerr.width(8);
        cerr.setf( std::ios::fixed, std:: ios::floatfield );
        cerr << "\tGB: " << margs->downloaded/1e9;
        cerr.width(18);
        cerr << "File: " << margs->downloaded*100/margs->file_size << " %";
        cerr << "\r";
    }
    cerr << endl;
    return NULL;
}

EXTERN int get_client_margs_live(Client *client){
    return client->margs.live;
}

EXTERN int64_t get_client_margs_downloaded(Client *client){
    return client->margs.downloaded;
}
