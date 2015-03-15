#include <openssl/evp.h>
#include <openssl/crypto.h>
#include <time.h>
#include <limits.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <stdlib.h>
#include "crypto.h"

#define MUTEX_TYPE         pthread_mutex_t
#define MUTEX_SETUP(x)     pthread_mutex_init(&(x), NULL)
#define MUTEX_CLEANUP(x)   pthread_mutex_destroy(&x)
#define MUTEX_LOCK(x)      pthread_mutex_lock(&x)
#define MUTEX_UNLOCK(x)    pthread_mutex_unlock(&x)
#define THREAD_ID          pthread_self()
#define AES_BLOCK_SIZE 8

static MUTEX_TYPE *mutex_buf = NULL;
static void locking_function(int mode, int n, const char*file, int line);
const int max_block_size = 64*1024;

ThreadedEncryption::ThreadedEncryption(int _direction,
                                       unsigned char* _key,
                                       int _n_threads)
{
    const EVP_CIPHER *cipher;
    n_threads = _n_threads;

    // Initialize thread arrays
    c_lock = new pthread_mutex_t[n_threads];
    thread_ready = new pthread_mutex_t[n_threads];
    ctx = new EVP_CIPHER_CTX[n_threads];
    e_args = new e_thread_args[n_threads];
    threads = new pthread_t[n_threads];

    // Setup OpenSSL for threads
    THREAD_setup();

    // Set cipher mode
    if (CTR_MODE){
        cipher = EVP_aes_128_ctr();
    } else {
        cipher = EVP_aes_128_cfb();
    }

    // EVP setup
    for (int i = 0; i < n_threads; i++){
        memset(ivec, 0, 1024);
        EVP_CIPHER_CTX_init(&ctx[i]);
        // Set encryption scheme
        if (!EVP_CipherInit_ex(&ctx[i], cipher, NULL, _key, ivec, _direction)) {
            fprintf(stderr, "error setting encryption scheme\n");
            exit(EXIT_FAILURE);
        }
    }

    // Initialize mutexes
    pthread_mutex_init(&id_lock, NULL);
    for (int i = 0; i < n_threads; i++){
        pthread_mutex_init(&c_lock[i], NULL);
        pthread_mutex_init(&thread_ready[i], NULL);
        pthread_mutex_lock(&thread_ready[i]);
    }

    // Initialize and set thread detached attribute
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
    thread_id = 0;

    // Initialize thread args
    for (int i = 0; i < n_threads; i++){
        e_args[i].thread_id = i;
        e_args[i].ctx = &ctx[i];
        e_args[i].c = this;
        int ret = pthread_create(&threads[i],
                                 &attr, &crypto_update_thread,
                                 &e_args[i]);
        if (ret){
            fprintf(stderr, "Unable to create thread: %d\n", ret);
        }
    }
}

int ThreadedEncryption::crypto_update(char* data, int len)
{
    int evp_outlen = 0;
    int i = get_thread_id();
    increment_thread_id();
    lock_data(i);

    if (len == 0) {

        // FINALIZE CIPHER
        if (!EVP_CipherFinal_ex(&ctx[i], (uchar*)data, &evp_outlen)) {
            fprintf(stderr, "encryption error\n");
            exit(EXIT_FAILURE);
        }

    } else {

        // [EN][DE]CRYPT
        if(!EVP_CipherUpdate(&ctx[i], (uchar*)data, &evp_outlen, (uchar*)data, len)){
            fprintf(stderr, "encryption error\n");
            exit(EXIT_FAILURE);
        }

        // DOUBLE CHECK
        if (evp_outlen-len){
            fprintf(stderr, "Did not encrypt full length of data [%d-%d]",
                    evp_outlen, len);
            exit(EXIT_FAILURE);
        }
    }

    unlock_data(i);
    return evp_outlen;

}

void *crypto_update_thread(void* _args)
{

    int evp_outlen = 0;

    if (!_args){
        fprintf(stderr, "Null argument passed to crypto_update_thread\n");
        exit(1);
    }

    e_thread_args* args = (e_thread_args*)_args;
    ThreadedEncryption *c = (ThreadedEncryption*)args->c;

    while (1) {
        int len = args->len;
        int total = 0;

        c->wait_thread_ready(args->thread_id);

        while (total < args->len){
            if(!EVP_CipherUpdate(&c->ctx[args->thread_id],
                                 args->data+total, &evp_outlen,
                                 args->data+total, args->len-total)){
                fprintf(stderr, "encryption error\n");
                exit(EXIT_FAILURE);
            }
            total += evp_outlen;
        }

        if (len != args->len){
            fprintf(stderr, "error: The length changed during encryption.\n\n");
            exit(1);
        }

        if (total != args->len){
            fprintf(stderr, "error: Did not encrypt full length of data %d [%d-%d]",
                    args->thread_id, total, args->len);
            exit(1);
        }

        c->unlock_data(args->thread_id);
    }

    return NULL;

}

int ThreadedEncryption::join_all_encryption_threads()
{
    for (int i = 0; i < n_threads; i++){
        lock_data(i);
        unlock_data(i);
    }
    return 0;
}

int ThreadedEncryption::pass_to_enc_thread(char* data, int len)
{
    if (len == 0)
        return 0;
    int thread_id = get_thread_id();
    lock_data(thread_id);
    increment_thread_id();
    e_args[thread_id].data = (uchar*) data;
    e_args[thread_id].len = len;
    set_thread_ready(thread_id);
    return 0;
}

/***********************************************************************
                    OpenSSL handling functions
************************************************************************/

// Function for OpenSSL to lock mutex
static void locking_function(int mode, int n, const char*file, int line)
{
    if (mode & CRYPTO_LOCK)
        MUTEX_LOCK(mutex_buf[n]);
    else
        MUTEX_UNLOCK(mutex_buf[n]);
}

// Returns the thread ID
static void threadid_func(CRYPTO_THREADID * id)
{
    // fprintf(stderr, "[debug] %s\n", "Passing thread ID");
    CRYPTO_THREADID_set_numeric(id, THREAD_ID);
}


int THREAD_setup(void)
{
    mutex_buf = (MUTEX_TYPE*)malloc(CRYPTO_num_locks()*sizeof(MUTEX_TYPE));

    if (!mutex_buf)
        return 0;

    int i;
    for (i = 0; i < CRYPTO_num_locks(); i++)
        MUTEX_SETUP(mutex_buf[i]);

    CRYPTO_THREADID_set_callback(threadid_func);
    CRYPTO_set_locking_callback(locking_function);
    return 0;
}

// Cleans up the mutex buffer for openSSL
int THREAD_cleanup(void)
{
    if (!mutex_buf)
        return 0;

    CRYPTO_THREADID_set_callback(NULL);
    CRYPTO_set_locking_callback(NULL);

    int i;
    for (i = 0; i < CRYPTO_num_locks(); i ++)
        MUTEX_CLEANUP(mutex_buf[i]);

    return 0;

}
