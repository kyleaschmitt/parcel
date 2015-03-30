/******************************************************************************
 *
 * FILE    : transcribers.cpp
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
 * DESCRIPTION : This file contains functions for proxying
 *               (transcribing the data) from transport protols to
 *               pipes or from pipes to transport protocols.
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


void *udt2pipe(void *_args_)
{
    /*
     *  udt2pipe() - Read from a UDT socket into a pipe
     *
     */
    udt_pipe_args_t *args = (udt_pipe_args_t*) _args_;
    char *buffer = (char*) malloc(BUFF_SIZE);
    int read_size;

    while (1){
        /* Read from UDT */
        read_size = UDT::recv(args->udt_socket, buffer, BUFF_SIZE, 0);
        if (UDT::ERROR == read_size) {
            if (UDT::getlasterror().getErrorCode() != 2001){
                error("recv: %s", UDT::getlasterror().getErrorMessage());
            }
            goto cleanup;
        }
        debug("Read %d bytes from UDT", read_size);

        /* Write to pipe */
        debug("Writing %d bytes to pipe", read_size);
        if (write(args->pipe, buffer, read_size) <= 0){
            debug("Failed to write to pipe.");
            goto cleanup;
        }
        debug("Writing %d bytes to pipe", read_size);
    }

 cleanup:
    debug("Exiting udt2pipe thread.");
    close(args->pipe);
    return NULL;
}

void *tcp2pipe(void *_args_)
{
    /*
     *  tcp2pipe() - Read from a TCP socket into a pipe
     *
     */
    tcp_pipe_args_t *args = (tcp_pipe_args_t*) _args_;
    char *buffer = (char*) malloc(BUFF_SIZE);
    int read_size;

    while (1){
        /* Read from TCP */
        if ((read_size = read(args->tcp_socket, buffer, BUFF_SIZE)) <= 0){
            debug("Unable to read from TCP socket.");
            goto cleanup;
        }
        debug("Read %d bytes from TCP socket %d", read_size, args->tcp_socket);

        /* Write to pipe */
        if (write(args->pipe, buffer, read_size) <= 0){
            debug("Failed to write to pipe");
            goto cleanup;
        }
        debug("Wrote %d bytes to pipe", read_size);
    }

 cleanup:
    debug("Exiting tcp2pipe thread.");
    close(args->pipe);
    return NULL;
}


int read_size_from_fd(int fd, char *buffer, int size, int sec, int usec){
    fd_set set;
    int total_read = 0;
    int read_size = 0;

    struct timeval timeout;
    timeout.tv_sec = sec;
    timeout.tv_usec = usec;

    /* Initialize the file descriptor set. */
    FD_ZERO(&set);
    FD_SET(fd, &set);

    debug("looking for %d", size);

    while (total_read < size){
        int select_res = select(FD_SETSIZE, &set, NULL, NULL, &timeout);
        if (select_res < 0){
            /* Error reading from pipe */
            perror("Unable to read from pipe");
            return total_read;
        } else if (select_res == 0) {
            /* We timed out, there is no more data for now */
            debug("No data to read, returning with %d bytes (%f)",
                  total_read, total_read*100./size);
            return total_read;
        } else {
            /* Read from pipe */
            int this_size = max(min(size-total_read, size), 0);
            if ((read_size = read(fd, buffer+total_read, this_size)) <= 0){
                debug("Unable to read from pipe.");
                return -1;
            }
            debug("Read intermediate %d from pipe", read_size);
            total_read += read_size;
        }
    }
    return total_read;
}

void *pipe2udt(void *_args_)
{
    /*
     *  pipe2udt() - Read from a pipe into a UDT socket
     *
     */
    udt_pipe_args_t *args = (udt_pipe_args_t*) _args_;
    int read_size;
    int temp_size;
    int this_size;

    int block_size = 128*1024*1024;
    char *buffer = (char*) malloc(block_size);
    int timeout = 1000;  // microseconds

    /* Initialize the timeout data structure. */
    while (1){

        read_size = read_size_from_fd(args->pipe, buffer, block_size, 0, timeout);
        if (read_size < 0){
            debug("Unable to read from pipe.");
            goto cleanup;
        }
        debug("Read %d bytes from pipe", read_size);

        /* Write to UDT */
        int sent_size = 0;
        debug("Writing %d bytes to UDT socket %d", read_size, args->udt_socket);
        while (sent_size < read_size) {
            this_size = min(read_size - sent_size, block_size);
            temp_size = UDT::send(args->udt_socket, buffer + sent_size, this_size, 0);
            if (UDT::ERROR == temp_size){
                error("send: %s", UDT::getlasterror().getErrorMessage());
                goto cleanup;
            }
            sent_size += temp_size;
        }
        debug("Wrote %d bytes to UDT", read_size);
    }

 cleanup:
    debug("Exiting pipe2udt thread.");
    free(buffer);
    UDT::close(args->udt_socket);
    close(args->pipe);
    return NULL;
}

void *pipe2tcp(void *_args_)
{
    /*
     *  pipe2tcp() - Read from a pipe into a UDT socket
     *
     */
    tcp_pipe_args_t *args = (tcp_pipe_args_t*) _args_;
    char *buffer = (char*) malloc(BUFF_SIZE);
    int read_size;
    int temp_size;
    int this_size;

    while (1){
        /* Read from pipe */
        if ((read_size = read(args->pipe, buffer, BUFF_SIZE)) <= 0){
            debug("Unable to read from pipe.");
            goto cleanup;
        }
        debug("Read %d bytes from pipe", read_size);

        /* Write to UDT */
        int sent_size = 0;
        debug("Writing %d bytes to TCP socket %d", read_size, args->tcp_socket);
        while (sent_size < read_size) {
            this_size = read_size - sent_size;
            temp_size = send(args->tcp_socket, buffer + sent_size, this_size, 0);
            if (temp_size < 0){
                error("unable to write to socket:");
                goto cleanup;
            }
            sent_size += temp_size;
        }
        debug("Wrote %d bytes to TCP", read_size);
    }

 cleanup:
    debug("Exiting pipe2tcp thread.");
    free(buffer);
    close(args->tcp_socket);
    close(args->pipe);
    return NULL;
}
