/******************************************************************************
 *
 * FILE    : parcel.h
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
 * DESCRIPTION : This file contains function definitions for starting
 *               proxy servers that translate between UDT and TCP.
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

#ifndef __PARCEL_H__
#define __PARCEL_H__

/* Standard libraries */
#include <unistd.h>
#include <cstdlib>
#include <cstring>
#include <netdb.h>
#include <sys/socket.h>
#include <iostream>
#include <assert.h>
#include <signal.h>

/* Non standard libraries */
#include <udt>

/******************************************************************************/
#define BUFF_SIZE 67108864
#define CIRCULAR_BUFF_SIZE 4*BUFF_SIZE
#define MSS 8400
#define EXTERN extern "C"
#define LOG

/* Uncomment this line and recompile to get verbose logging output */
/* #define DEBUG */

/******************************************************************************/
using namespace std;

/******************************************************************************
 * file: cbuffer.cpp
 *
 ******************************************************************************/
class CircularBuffer
{
public:
    CircularBuffer(size_t capacity);
    ~CircularBuffer();

    /* True if there is space is available to write to */
    bool has_space () const { return (capacity_ - size_ > 1); }
    /* How many bytes are currently in the buffer */
    size_t size      () const { return size_;     }
    /* Total capacity */
    size_t capacity  () const { return capacity_; }
    /* Close the buffer */
    void   close     ()       { closed_ = true;   }
    size_t read_nonblocking(char *data, size_t bytes);
    size_t write_nonblocking(const char *data, size_t bytes);
    /* Return number of bytes written. */
    size_t write(const char *data, size_t bytes);
    /* Return number of bytes read. */
    size_t read(char *data, size_t bytes);
    void wait_for_space();
    void wait_for_data();
    void signal_space();
    void signal_data();

private:
    size_t beg_index_, end_index_, size_, capacity_;
    pthread_cond_t space_cond_, data_cond_;
    pthread_mutex_t cond_mutex_, pointer_mutex_;
    bool closed_;
    char *data_;
};

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
    CircularBuffer *pipe;
} udt_pipe_args_t;

typedef struct tcp_pipe_args_t {
    int tcp_socket;
    CircularBuffer *pipe;
} tcp_pipe_args_t;

/******************************************************************************
 * file: udt2tcp.cpp
 *
 * udt2tcp_start() - This is the main function for starting a UDT
 *                   proxy server on the local. Arguments specify the
 *                   local hostname and port for the UDT server to
 *                   bind to, as well as the remote hostname and port
 *                   that a TCP connection will reach out to once a
 *                   UDT client is recieved.
 *
 ******************************************************************************/
EXTERN int udt2tcp_start(char *local_host, char *local_port, char *remote_host, char *remote_port);
int connect_remote_tcp(transcriber_args_t *args);
void *thread_udt2tcp(void *_args_);
EXTERN void *udt2tcp_accept_clients(void *_args_);

/******************************************************************************
 * file: udt2tcp.cpp
 *
 * udt2tcp_start() - This is the main function for starting a TCP
 *                   proxy server on the local. Arguments specify the
 *                   local hostname and port for the TCP server to
 *                   bind to, as well as the remote hostname and port
 *                   that a UDT connection will reach out to once a
 *                   TCP client is recieved.
 *
 ******************************************************************************/
EXTERN int tcp2udt_start(char *local_host, char *local_port, char *remote_host, char *remote_port);
int connect_remote_udt(transcriber_args_t *args);
void *thread_tcp2udt(void *_args_);
EXTERN void *tcp2udt_accept_clients(void *_args_);


/******************************************************************************
 * file: trascribers.cpp - These methods are written to be called as
 *                         threads (though they are called directly as
 *                         well) to translate a protocol to a system
 *                         pipe or a system pipe to a protocol.
 ******************************************************************************/
void *udt2pipe(void *_args_);
void *tcp2pipe(void *_args_);
void *pipe2udt(void *_args_);
void *pipe2tcp(void *_args_);

/******************************************************************************
 * macros - Macros for logging
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
