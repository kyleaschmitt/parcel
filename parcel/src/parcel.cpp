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

class Server;
class ServerThread;
class Client;

void* recvdata(void*);
void* monitor(void* margs);
EXTERN int send_data_no_encryption(UDTSOCKET socket, char *data, int size);
EXTERN int read_data_no_encryption(UDTSOCKET socket, char *data, int size);
EXTERN int read_size_no_encryption(UDTSOCKET socket, char *buff, int len);
EXTERN int read_data(ThreadedEncryption *decryptor, UDTSOCKET socket,
                     char *buff, int len);
EXTERN int read_size(ThreadedEncryption *decryptor, UDTSOCKET socket,
                     char *buff, int len);
EXTERN int send_data(ThreadedEncryption *encryptor, UDTSOCKET socket,
                     char *buff, int len);


/***********************************************************************
 *                               Server
 ***********************************************************************/

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

    // Setup address information
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags = AI_PASSIVE;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
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

/***********************************************************************
 *                          Server C Wrappers
 ***********************************************************************/


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

/***********************************************************************
 *                           Server Thread
 ***********************************************************************/

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


ServerThread *Server::next_client()
{

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

ServerThread::ServerThread(UDTSOCKET *usocket, char *host, char *port)
{
    memcpy(clienthost, host, NI_MAXHOST);
    memcpy(clientport, port, NI_MAXSERV);
    recver = *(UDTSOCKET*)usocket;
    delete (UDTSOCKET*)usocket;
}

int ServerThread::close(){
    return UDT::close(recver);
}

/***********************************************************************
 *                      ServerThread Wrappers
 ***********************************************************************/

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

/***********************************************************************
 *                               Client
 ***********************************************************************/

class Client
{
public:
    int blast;
    int blast_rate;
    int udt_buff;
    int udp_buff;
    int mss;
    UDTSOCKET client;
    int live;
    int64_t downloaded;
    int64_t file_size;


    Client();
    int close();
    int start(char *host, char *port);
};


Client::Client()
{
    live = 0;
    downloaded = 0;
    file_size = 0;
    blast = 0;
    blast_rate = 0;
    udt_buff = BUFF_SIZE;
    udp_buff = BUFF_SIZE;
    mss = MSS;
}

int Client::start(char *host, char *port)
{
    struct addrinfo hints, *local, *peer;

    // Setup address information
    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_flags = AI_PASSIVE;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (0 != getaddrinfo(NULL, port, &hints, &local)){
        cerr << "incorrect network address.\n" << endl;
        return -1;
    }

    // Connect to server
    client = UDT::socket(local->ai_family, local->ai_socktype,
                         local->ai_protocol);
    // We are not done with local
    freeaddrinfo(local);

    // Set socket options
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
    // We are now done with peer
    freeaddrinfo(peer);

    return 0;
}

int Client::close()
{
    UDT::close(client);
    return 0;
}

/***********************************************************************
 *                        Client C Wrappers
 ***********************************************************************/

EXTERN Client* new_client(){
    return new Client();
}

EXTERN int client_start(Client *client, char *host, char *port){
    return client->start(host, port);
}

EXTERN UDTSOCKET client_get_socket(Client *client){
    return client->client;
}

EXTERN long long client_recv_file(ThreadedEncryption *decryptor, Client *client,
                                  char *path, int64_t size,
                                  int64_t block_size, int print_stats)
{
    char *buffer = new char[block_size];

    // Open the output file
    fstream ofs(path, ios::out | ios::binary | ios::trunc);

    // Set information on the client for external monitoring
    client->downloaded = 0;
    client->live = 1;

    // Start reading the file
    while (client->downloaded < size){
        // Read in the next block
        int64_t this_size = min(size-client->downloaded, block_size);
        int rs = read_size(decryptor, client->client, buffer, this_size);
        // Check the read
        if (rs < 0){
            cerr << "Unable to write to file: " << path << endl;
            return rs;
        }
        // Try to write to file
        if (!ofs.write(buffer, rs)){
            cerr << "Unable to write to file: " << path << endl;
            return -1;
        }
        // Increment counter
        client->downloaded += rs;
    }
    // Close the file
    ofs.close();
    // Delete our buffer
    delete buffer;
    // Tell any external monitors that we are done
    client->live = 0;
    // Return the total amount downloaded
    return client->downloaded;
}

EXTERN int get_client_live(Client *client){
    return client->live;
}

EXTERN int64_t get_client_downloaded(Client *client){
    return client->downloaded;
}

EXTERN int client_close(Client *client){
    client->close();
    delete client;
    return 0;
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
            return -1;
        }
        // Increment the amount sent before repeating
        ssize += ss;
    }
    return ssize;
}

EXTERN int read_data_no_encryption(UDTSOCKET socket, char *buff, int len)
{
    assert(len >= 0);
    int rs = 0;
    if (UDT::ERROR == (rs = UDT::recv(socket, buff, len, 0))){
        if (UDT::getlasterror().getErrorCode() != 2001)
            cerr << "recv:" << UDT::getlasterror().getErrorMessage() << endl;
        return -1;
    }
    return rs;
}

EXTERN int read_size_no_encryption(UDTSOCKET socket, char *buff, int len)
{
    assert(len >= 0);
    int total_read = 0;
    int rs = 0;

    while (total_read < len){
        if ((rs = read_data_no_encryption(socket, buff+rs, len - rs)) < 0){
            cerr << "Unable to read from socket" << endl;
            return rs;
        }
        total_read += rs;
    }
    return total_read;
}

EXTERN int read_data(ThreadedEncryption *decryptor, UDTSOCKET socket,
                     char *buff, int len)
{
    int total_read;
    if (len != (total_read = read_data_no_encryption(socket, buff, len))){
        cerr << "Invalid read." << endl;
        return total_read;
    }
    decryptor->map(buff, buff, total_read);
    return total_read;
}

EXTERN int read_size(ThreadedEncryption *decryptor, UDTSOCKET socket,
                     char *buff, int len)
{
    int total_read;
    // Read data from UDT socket and check length
    if (len != (total_read = read_size_no_encryption(socket, buff, len))){
        cerr << "Invalid read: " << total_read << " != " << len << endl;
        return total_read;
    }
    // Decrypt the data in place
    if (len != decryptor->map(buff, buff, total_read)){
        cerr << "Invalid decrypt: " << total_read << " != " << len << endl;
        return total_read;
    }
    // Return the total_read
    return total_read;
}

EXTERN int send_data(ThreadedEncryption *encryptor, UDTSOCKET socket,
                     char *buff, int len)
{
    // Encrypt the buffer in place
    encryptor->map(buff, buff, len);
    // Send data over UDT socket
    int total_sent = send_data_no_encryption(socket, buff, len);
    // Check send length
    if (total_sent != len){
        cerr << "Invalid write: " << total_sent << " != " << len << endl;
        return total_sent;
    }
    return total_sent;
}


/***********************************************************************
 *                        Encryption Wrappers
 ***********************************************************************/

EXTERN ThreadedEncryption *encryption_init(char *key, char *iv)
{
    return new ThreadedEncryption(EVP_ENCRYPT,
                                  (unsigned char*)key,
                                  (unsigned char*)iv,
                                  0);
}

EXTERN ThreadedEncryption *decryption_init(char *key, char *iv)
{
    return new ThreadedEncryption(EVP_DECRYPT,
                                  (unsigned char*)key,
                                  (unsigned char*)iv,
                                  0);
}
