/******************************************************************************
 *
 * FILE    : cbuffer.h
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
 * DESCRIPTION : This file contains CircularBuffer class
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

class CircularBuffer
{
public:
    CircularBuffer(size_t capacity);
    ~CircularBuffer();

    /* True if there is space is available to write to */
    bool has_space () const { return (capacity_ - size_ > 1); }
    /* How many bytes are currently in the buffer */
    size_t size () const { return size_;     }
    /* Total capacity */
    size_t capacity () const { return capacity_; }
    /* Close the buffer */
    void close () { closed_ = true;   }
    /* Return number of bytes read. */
    size_t read_nonblocking(char *data, size_t bytes);
    /* Return number of bytes written. */
    size_t write_nonblocking(const char *data, size_t bytes);
    /* Return number of bytes written. */
    size_t write(const char *data, size_t bytes);
    /* Return number of bytes read. */
    size_t read(char *data, size_t bytes);
    /* Wait until there is space to write */
    void wait_for_space();
    /* Wait until there is data to read */
    void wait_for_data();
    /* Signal that there is space to write */
    void signal_space();
    /* Signal that there is data to read */
    void signal_data();

private:
    size_t beg_index_, end_index_, size_, capacity_;
    pthread_cond_t space_cond_, data_cond_;
    pthread_mutex_t cond_mutex_, pointer_mutex_;
    bool closed_;
    char *data_;
};
