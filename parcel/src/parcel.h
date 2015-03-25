/*******************************************************************************
 * parcel.h
 *
 * Header file for parcel.
 *
 ******************************************************************************/

#ifndef __PARCEL_H__
#define __PARCEL_H__

#ifndef WIN32
#include <unistd.h>
#include <cstdlib>
#include <cstring>
#include <netdb.h>
#include <sys/socket.h>
#else
#include <winsock2.h>
#include <ws2tcpip.h>
#include <wspiapi.h>
#endif
#include <iostream>
#include <assert.h>

#include <udt>

/******************************************************************************/
#define BUFF_SIZE 67108864
#define MSS 8400
#define EXTERN extern "C"
#define LOG
/* #define DEBUG */

/******************************************************************************/
using namespace std;

/******************************************************************************
 * thread arg structures
 ******************************************************************************/
typedef struct server_args_t {
    UDTSOCKET udt_socket;
    int tcp_socket;
    char *remote_host;
    char *remote_port;
} server_args_t;

typedef struct transcriber_args_t {
    UDTSOCKET udt_socket;
    int tcp_socket;
    char *remote_host;
    char *remote_port;
} udt2tcp_args_t;

typedef struct udt_pipe_args_t {
    UDTSOCKET udt_socket;
    int pipe;
} udt_pipe_args_t;

typedef struct tcp_pipe_args_t {
    int tcp_socket;
    int pipe;
} tcp_pipe_args_t;

/******************************************************************************
 * file: udt2tcp.cpp
 ******************************************************************************/
EXTERN int udt2tcp_start(char *local_host, char *local_port, char *remote_host, char *remote_port);
int connect_remote_tcp(transcriber_args_t *args);
void *thread_udt2tcp(void *_args_);
EXTERN void *udt2tcp_accept_clients(void *_args_);

/******************************************************************************
 * file: tcp2udt.cpp
 ******************************************************************************/
EXTERN int tcp2udt_start(char *local_host, char *local_port, char *remote_host, char *remote_port);
int connect_remote_udt(transcriber_args_t *args);
void *thread_tcp2udt(void *_args_);
EXTERN void *tcp2udt_accept_clients(void *_args_);

/******************************************************************************
 * file: parcel.cpp
 ******************************************************************************/
EXTERN int server_start(char *local_host, char *local_port, char *remote_host, char *remote_port);
EXTERN int client_start(char *local_host, char *local_port, char *remote_host, char *remote_port);

/******************************************************************************
 * Methods for transcribing to and from pipes, TCP, and UDT
 * file: trascribers.cpp
 ******************************************************************************/
void *udt2pipe(void *_args_);
void *tcp2pipe(void *_args_);
void *pipe2udt(void *_args_);
void *pipe2tcp(void *_args_);


/******************************************************************************
 * macros
 ******************************************************************************/
#ifdef LOG
#define log(fmt, ...)                                      \
    do {                                                   \
        fprintf(stderr, "[parcel][%s][INFO] ", __func__);  \
        fprintf(stderr, fmt, ##__VA_ARGS__);               \
        fprintf(stderr, "\n");                             \
    } while(0)
#else
#define log(fmt, ...)
#endif

#ifdef DEBUG
#define debug(fmt, ...)                                     \
    do {                                                    \
        fprintf(stderr, "[parcel][%s][DEBUG] ", __func__);  \
        fprintf(stderr, fmt, ##__VA_ARGS__);                \
        fprintf(stderr, "\n");                              \
    } while(0)
#else
#define debug(fmt, ...)
#endif

#define error(fmt, ...)                                     \
    do {                                                    \
        fprintf(stderr, "[parcel][%s][ERROR] ", __func__);  \
        fprintf(stderr, fmt, ##__VA_ARGS__);                \
        fprintf(stderr, "\n");                              \
    } while(0)


#endif  //__PARCEL_H__
