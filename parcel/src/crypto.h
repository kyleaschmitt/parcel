/*****************************************************************************
Copyright 2012 Laboratory for Advanced Computing at the University of Chicago

This file is part of UDR.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions
and limitations under the License.
*****************************************************************************/
#ifndef CRYPTO_H
#define CRYPTO_H

#define MAX_CRYPTO_THREADS 32
#define USE_CRYPTO 1

#define EVP_ENCRYPT 1
#define EVP_DECRYPT 0
#ifndef OPENSSL_HAS_CTR
#define CTR_MODE 0
#else
#define CTR_MODE 1
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <openssl/err.h>
#include <limits.h>
#include <iostream>
#include <unistd.h>
#include <semaphore.h>

#define MUTEX_TYPE          pthread_mutex_t
#define MUTEX_SETUP(x)      pthread_mutex_init(&(x), NULL)
#define MUTEX_CLEANUP(x)    pthread_mutex_destroy(&x)
#define MUTEX_LOCK(x)       pthread_mutex_lock(&x)
#define MUTEX_UNLOCK(x)     pthread_mutex_unlock(&x)
#define THREAD_ID           pthread_self()

#define KEY_SIZE 256

int THREAD_setup(void);
int THREAD_cleanup(void);
void *enrypt_threaded(void* _args);


using namespace std;

typedef unsigned char uchar;

typedef struct e_thread_args
{
    uchar *data;
    uchar *dest;
    int len;
    EVP_CIPHER_CTX *ctx;
    int idle;
    void* c;
    int thread_id;
} e_thread_args;

void *crypto_update_thread(void* _args);

class ThreadedEncryption
{
 private:
    pthread_mutex_t *c_lock;
    pthread_mutex_t *thread_ready;
    unsigned char ivec[1024];
    pthread_mutex_t id_lock;
    int n_threads;
    int thread_id;

 public:

    EVP_CIPHER_CTX *ctx;
    e_thread_args *e_args;
    pthread_t *threads;
    ThreadedEncryption(int direc,
                       unsigned char* key,
                       int n_threads);

    ThreadedEncryption(){}


    int crypto_update(char *data, char *dest, int len);
    int join_all_encryption_threads();
    int pass_to_enc_thread(char *data, char *dest, int len);
    int map(char* data, char *dest, int len);
    int map_threaded(char* data, char *dest, int len);

    int get_num_crypto_threads(){
        return n_threads;
    }

    int get_thread_id(){
        pthread_mutex_lock(&id_lock);
        int id = thread_id;
        pthread_mutex_unlock(&id_lock);
        return id;
    }

    int increment_thread_id(){
        pthread_mutex_lock(&id_lock);
        thread_id++;
        if (thread_id >= n_threads)
            thread_id = 0;
        pthread_mutex_unlock(&id_lock);
        return 1;
    }

    int set_thread_ready(int thread_id){
        return pthread_mutex_unlock(&thread_ready[thread_id]);
    }

    int wait_thread_ready(int thread_id){
        return pthread_mutex_lock(&thread_ready[thread_id]);
    }

    int lock_data(int thread_id){
        return pthread_mutex_lock(&c_lock[thread_id]);
    }

    int unlock_data(int thread_id){
        return pthread_mutex_unlock(&c_lock[thread_id]);
    }
};

void *crypto_update_thread(void* _args);

#endif
