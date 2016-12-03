#define ICY_META_BUF_SIZE 512000

#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* data: body data of current callback,
   size: size of char,
   count: count of bytes in current callback,
   store: can be used to pass in a pointer for subsequently storing transferred
   data*/
size_t icy_meta_header_callback(char *data, size_t size, size_t count,
                                void *store);
size_t icy_meta_write_callback(char *data, size_t size, size_t count,
                               void *store);

char icy_meta_buf[ICY_META_BUF_SIZE];
size_t icy_meta_buf_len = 0;
size_t icy_meta_interval = 0;

size_t icy_meta_header_callback(char *data, size_t size, size_t count,
                                void *nouse) {
  size_t data_len = size * count;

  /* parse number received in icy-metaint header to long and store in
   * icy_meta_interval
   */
  if (memcmp("icy-metaint:", data, 12) == 0) {
    char icy_meta_interval_str[data_len - 12];
    memcpy(icy_meta_interval_str, &data[12], data_len - 12);
    icy_meta_interval = atol(icy_meta_interval_str);
  }

  return data_len;
}

size_t icy_meta_write_callback(char *data, size_t size, size_t count,
                               void *nouse) {
  size_t data_len = size * count;

  /* append all received data in current callback to icy_meta_buf and increment
   * icy_meta_buf_len by length of received data */
  memcpy(&icy_meta_buf[icy_meta_buf_len], data, data_len);
  icy_meta_buf_len += data_len;

  /* when enough bytes where received and the meta data lenght is not 0 proceed
   * with attempt to get all the meta data*/
  if (icy_meta_buf_len >= icy_meta_interval &&
      icy_meta_buf[icy_meta_interval] != 0) {
    size_t icy_meta_len = icy_meta_buf[icy_meta_interval] * 16 + 1;

    /* when all of the meta data string can be retreived proceed */
    if (icy_meta_buf_len > icy_meta_interval + icy_meta_len) {
      /* print meta data string */
      char icy_meta_data[icy_meta_len];
      memcpy(icy_meta_data, &icy_meta_buf[icy_meta_interval + 1], icy_meta_len);
      puts(icy_meta_data);
      fflush(stdout);

      /* get offset of adajacent audio data after nullbyte and insert it at
       * begin of icy_meta_buf; this is needed to get the location of the next
       * icy meta interval right which could in theory already be present if the
       * current callback data was long enough */
      size_t icy_audio_offset = icy_meta_interval + icy_meta_len;
      size_t icy_audio_len = icy_meta_buf_len - icy_audio_offset;
      char tmp_buf[ICY_META_BUF_SIZE];
      memcpy(tmp_buf, &icy_meta_buf[icy_audio_offset], icy_audio_len);
      memcpy(icy_meta_buf, tmp_buf, icy_audio_len);
      icy_meta_buf_len = icy_audio_len;
    }
  }

  /* if no metdata is currently embeded in the stream, 0 will be present at the
   * icy-metaint location; there is no nullbyte padding after the icy meta
   * interval and copying the leftover data of the current callback can start
   * right after icy meta interval location */
  if (icy_meta_buf_len > icy_meta_interval &&
      icy_meta_buf[icy_meta_interval] == 0) {
    size_t icy_audio_offset = icy_meta_interval + 1;
    size_t icy_audio_len = icy_meta_buf_len - icy_audio_offset;

    char tmp_buf[ICY_META_BUF_SIZE];
    memcpy(tmp_buf, &icy_meta_buf[icy_audio_offset], icy_audio_len);
    memcpy(icy_meta_buf, tmp_buf, icy_audio_len);
    icy_meta_buf_len = icy_audio_len;
  }

  return data_len;
}

int main(int argc, char **argv) {
  CURL *curl_handle = NULL;
  struct curl_slist *request_headers = NULL;

  /* set icy metadata request header to receive icy-metaint in the response
   * headers */
  request_headers = curl_slist_append(request_headers, "Icy-MetaData:1");

  curl_handle = curl_easy_init();

  /* set request headers */
  curl_easy_setopt(curl_handle, CURLOPT_HTTPHEADER, request_headers);

  /* set url */
  curl_easy_setopt(curl_handle, CURLOPT_URL, argv[1]);

  /* follow redirects */
  curl_easy_setopt(curl_handle, CURLOPT_FOLLOWLOCATION, 1L);

  /* set response header callback */
  curl_easy_setopt(curl_handle, CURLOPT_HEADERFUNCTION,
                   icy_meta_header_callback);

  /* set response body callback */
  curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION, icy_meta_write_callback);

  /* make request */
  curl_easy_perform(curl_handle);

  /* cleanup curl stuff */
  curl_slist_free_all(request_headers);
  curl_easy_cleanup(curl_handle);

  return 0;
}
