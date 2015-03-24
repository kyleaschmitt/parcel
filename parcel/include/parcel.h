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
#else
#include <winsock2.h>
#include <ws2tcpip.h>
#include <wspiapi.h>
#endif
#include <iostream>
#include <assert.h>
#include <udt.h>

/******************************************************************************/
#define BUFF_SIZE 67108864
#define MSS 8400
#define EXTERN extern "C"

/******************************************************************************/
using namespace std;

/******************************************************************************/
typedef struct udt2tcp_args_t {
    UDTSOCKET udt_socket;
    char *remote_host;
    char *remote_port;
} udt2tcp_args_t;

typedef struct tcp2udt_args_t {
    int tcp_socket;
    char *remote_host;
    char *remote_port;
} tcp2udt_args_t;

/******************************************************************************/
EXTERN int proxy_start(char *local_host, char *local_port, char *remote_host, char *remote_port);
EXTERN void * thread_udt2tcp_start(void *_args_);

#endif  //__PARCEL_H__
