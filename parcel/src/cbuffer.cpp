/*
 * File taken from
 * http://www.asawicki.info/news_1468_circular_buffer_of_raw_binary_data_in_c.html
 * and modified to be thread safe for posix systems and to block on
 * write
 */
#include "parcel.h"

CircularBuffer::CircularBuffer(size_t capacity)
    : beg_index_(0)
    , end_index_(0)
    , size_(0)
    , capacity_(capacity)
   , closed_(false)
{
    data_ = new char[capacity];
    if (pthread_cond_init(&space_cond_, NULL)){
        perror("error initializing space_cond_");
    }
    if (pthread_cond_init(&data_cond_, NULL)){
        perror("error initializing data_cond_");
    }
    if (pthread_mutex_init(&cond_mutex_, NULL)){
        perror("error initializing pthread_mutex");
    }
    if (pthread_mutex_init(&pointer_mutex_, NULL)){
        perror("error initializing pthread_mutex");
    }
}

CircularBuffer::~CircularBuffer()
{
    /* pthread_mutex_destroy(&); */
    /* pthread_cond_destroy(&cbc->notfull); */
    /* pthread_cond_destroy(&cbc->notempty); */
    delete [] data_;
}

/******************************************************************************
 * Writing data
 ******************************************************************************/

size_t CircularBuffer::write_nonblocking(const char *data, size_t bytes)
{
    if (bytes == 0){ return  0; }
    if (closed_)   { return -1; }

    /* Lock and calculate sizes */
    pthread_mutex_lock(&pointer_mutex_);
    size_t capacity        = capacity_;
    size_t bytes_to_write  = std::min(bytes, capacity - size_);
    size_t size_1          = capacity - end_index_;
    size_t size_2          = bytes_to_write - size_1;
    bool   single_step     = (bytes_to_write <= capacity - end_index_);
    pthread_mutex_unlock(&pointer_mutex_);

    /* Short circuit, there's no more space */
    if (bytes_to_write == 0){ return  0; }

    /* Write data */
    if (single_step){
        memcpy(data_ + end_index_, data, bytes_to_write);
    } else {
        memcpy(data_ + end_index_, data, size_1);
        memcpy(data_, data + size_1, size_2);
    }

    /* Update pointers */
    pthread_mutex_lock(&pointer_mutex_);
    if (single_step){
        end_index_ += bytes_to_write;
        /* Loop back */
        if (end_index_ == capacity){
            end_index_ = 0;
        }
    } else {
        end_index_ = size_2;
    }
    size_ += bytes_to_write;
    pthread_mutex_unlock(&pointer_mutex_);

    return bytes_to_write;
}

size_t CircularBuffer::write(const char *data, size_t bytes)
{
    if (bytes == 0){ return  0; }
    if (closed_)   { return -1; }

    debug("Writing %li bytes to CircularBuffer %p", bytes, this);
    size_t bytes_written = 0;
    if (!has_space()){
        wait_for_space();
    }

    while (bytes_written < bytes){
        if (!has_space()){
            wait_for_space();
        }
        size_t written_this_time = write_nonblocking(data  + bytes_written,
                                                     bytes - bytes_written);
        bytes_written += written_this_time;
        debug("Wrote %li bytes to CircularBuffer %p", written_this_time, this);
    }
    if (bytes_written > 0) {
        signal_data();
    }
    return bytes_written;
}

/******************************************************************************
 * Reading data
 ******************************************************************************/

size_t CircularBuffer::read_nonblocking(char *data, size_t bytes)
{
    if (bytes == 0){ return  0; }
    if (closed_)   { return -1; }

    pthread_mutex_lock(&pointer_mutex_);
    size_t capacity       = capacity_;
    size_t bytes_to_read  = std::min(bytes, size_);
    size_t size_1         = capacity - beg_index_;
    size_t size_2         = bytes_to_read - size_1;
    bool   single_step    = (bytes_to_read <= capacity - beg_index_);
    pthread_mutex_unlock(&pointer_mutex_);

    /* Read data */
    if (single_step){
        memcpy(data, data_ + beg_index_, bytes_to_read);
    } else {
        memcpy(data, data_ + beg_index_, size_1);
        memcpy(data + size_1, data_, size_2);
    }

    /* Update pointers */
    pthread_mutex_lock(&pointer_mutex_);
    if (single_step){
        beg_index_ += bytes_to_read;
        /* Loop back */
        if (beg_index_ == capacity){
            beg_index_ = 0;
        }
    } else {
        beg_index_ = size_2;
    }
    size_ -= bytes_to_read;
    pthread_mutex_unlock(&pointer_mutex_);

    debug("Read %li bytes from CircularBuffer %p", bytes_to_read, this);

    return bytes_to_read;
}

size_t CircularBuffer::read(char *data, size_t bytes)
{
    if (!size()){
        wait_for_data();
    }
    size_t bytes_read = read_nonblocking(data, bytes);
    if (bytes_read > 0) {
        signal_space();
    }
    return bytes_read;
}

/******************************************************************************
 * Condition variable handling
 ******************************************************************************/

void CircularBuffer::wait_for_space()
{
    pthread_mutex_lock(&cond_mutex_);
    while (!has_space()){
        pthread_cond_wait(&space_cond_, &cond_mutex_);
    }
    pthread_mutex_unlock(&cond_mutex_);
}

void CircularBuffer::wait_for_data()
{
    pthread_mutex_lock(&cond_mutex_);
    while (!size()){
        pthread_cond_wait(&data_cond_, &cond_mutex_);
    }
    pthread_mutex_unlock(&cond_mutex_);
}

void CircularBuffer::signal_space()
{
    pthread_mutex_lock(&cond_mutex_);
    pthread_cond_signal(&space_cond_);
    pthread_mutex_unlock(&cond_mutex_);
}

void CircularBuffer::signal_data()
{
    pthread_mutex_lock(&cond_mutex_);
    pthread_cond_signal(&data_cond_);
    pthread_mutex_unlock(&cond_mutex_);
}
