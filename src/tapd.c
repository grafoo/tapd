#define ICY_META_BUF_SIZE 512000
#define _XOPEN_SOURCE   /* needed for time functions e.g. strptime */
#define _DEFAULT_SOURCE /* needed for strsep */

#include "mongoose/mongoose.h"
#include <curl/curl.h>
#include <glib.h>
#include <gst/gst.h>
#include <jansson.h>
#include <mxml.h>
#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* data: body data of current callback,
   size: size of char,
   count: count of bytes in current callback,
   store: can be used to pass in a pointer for subsequently storing transferred
   data*/
size_t icy_meta_header_callback(char *data, size_t size, size_t count,
                                void *store);
size_t icy_meta_write_callback(char *data, size_t size, size_t count,
                               void *store);

static void handle_mongoose_event(struct mg_connection *connection, int event,
                                  void *event_data);

static gboolean gstreamer_bus_call(GstBus *bus, GstMessage *msg, gpointer data);

void play_audio(char *uri);
void pause_audio();
void stop_audio();

struct radio {
  char *name;
  size_t name_len;
  char *stream_uri;
  size_t stream_uri_len;
};

void select_radios_num(int *radios_num);
void select_radios(struct radio radios[]);

struct feed {
  int id;
  char *uri;
};

void select_feeds(struct feed **feeds, int *feeds_num);
void select_feed(struct feed *feed, int id);

char icy_meta_buf[ICY_META_BUF_SIZE];
size_t icy_meta_buf_len = 0;
size_t icy_meta_interval = 0;

static struct mg_serve_http_opts mongoose_http_server_options;
static const struct mg_str mongoose_http_method_get = MG_MK_STR("GET");
static const struct mg_str mongoose_http_method_post = MG_MK_STR("POST");

GMainLoop *loop;
GstElement *pipeline;
int playing = 0;

struct membuf {
  char *string;
  size_t size;
};

static size_t get_feed_xml_write_callback(void *data, size_t size, size_t count,
                                          void *membuf);

struct query_param {
  char *key;
  char *val;
};

void extract_params(struct query_param **query_params, char *query_string,
                    size_t *query_params_len);

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

void select_feeds(struct feed **feeds, int *feeds_num) {
  sqlite3 *db;
  sqlite3_stmt *stmt;
  int i;

  if (sqlite3_open("tapd.db", &db) != SQLITE_OK) {
    printf("failed to open database: %s\n", sqlite3_errmsg(db));
    exit(1);
  }

  if (sqlite3_prepare_v2(db, "select id, uri from feeds", -1, &stmt, NULL) !=
      SQLITE_OK) {
    printf("failed to prepare statement: %s\n", sqlite3_errmsg(db));
    sqlite3_close(db);
  }

  for (i = 0; sqlite3_step(stmt) == SQLITE_ROW; i++) {
    struct feed *tmp = realloc(*feeds, (*feeds_num + 1) * sizeof(struct feed));
    if (tmp == NULL) {
      puts("failed allocating memory for feeds struct");
      exit(1);
    } else {
      *feeds = tmp;
    }

    (*feeds)[*feeds_num].id = sqlite3_column_int(stmt, 0);
    (*feeds)[*feeds_num].uri =
        strdup((const char *)sqlite3_column_text(stmt, 1));
    (*feeds_num)++;
  }

  sqlite3_finalize(stmt);
  sqlite3_close(db);
}

void select_feed(struct feed *feed, int id) {
  sqlite3 *db;
  sqlite3_stmt *stmt;

  if (sqlite3_open("tapd.db", &db) != SQLITE_OK) {
    printf("failed to open database: %s\n", sqlite3_errmsg(db));
    exit(1);
  }

  if (sqlite3_prepare_v2(db, "select uri from feeds where id = ?", -1, &stmt,
                         NULL) != SQLITE_OK) {
    printf("failed to prepare statement: %s\n", sqlite3_errmsg(db));
    sqlite3_close(db);
  }

  sqlite3_bind_int(stmt, 1, id);

  if (sqlite3_step(stmt) == SQLITE_ROW) {
    feed->uri = strdup((const char *)sqlite3_column_text(stmt, 0));
  }

  sqlite3_finalize(stmt);
  sqlite3_close(db);
}

void select_radios_num(int *radios_num) {
  sqlite3 *db;
  sqlite3_stmt *stmt;

  if (sqlite3_open("tapd.db", &db) != SQLITE_OK) {
    printf("failed to open database: %s\n", sqlite3_errmsg(db));
    exit(1);
  }

  if (sqlite3_prepare_v2(db, "select count(id) from radios", -1, &stmt, NULL) !=
      SQLITE_OK) {
    printf("failed to prepare statement: %s\n", sqlite3_errmsg(db));
    sqlite3_close(db);
  }

  sqlite3_step(stmt);
  *radios_num = sqlite3_column_int(stmt, 0);

  sqlite3_finalize(stmt);
  sqlite3_close(db);
}

void select_radios(struct radio radios[]) {
  sqlite3 *db;
  sqlite3_stmt *stmt;

  if (sqlite3_open("tapd.db", &db) != SQLITE_OK) {
    printf("failed to open database: %s\n", sqlite3_errmsg(db));
    exit(1);
  }

  if (sqlite3_prepare_v2(db, "select name, stream_uri from radios", -1, &stmt,
                         NULL) != SQLITE_OK) {
    printf("failed to prepare statement: %s\n", sqlite3_errmsg(db));
    sqlite3_close(db);
  }

  int i;
  for (i = 0; sqlite3_step(stmt) == SQLITE_ROW; i++) {
    const char *radio_name = (const char *)sqlite3_column_text(stmt, 0);
    size_t radio_name_len = strlen(radio_name);

    const char *radio_stream_uri = (const char *)sqlite3_column_text(stmt, 1);
    size_t radio_stream_uri_len = strlen(radio_stream_uri);

    radios[i].name = malloc(radio_name_len * sizeof(char));
    memcpy(radios[i].name, radio_name, radio_name_len);
    radios[i].name_len = radio_name_len;

    radios[i].stream_uri = malloc(radio_stream_uri_len * sizeof(char));
    memcpy(radios[i].stream_uri, radio_stream_uri, radio_stream_uri_len);
    radios[i].stream_uri_len = radio_stream_uri_len;
  }

  sqlite3_finalize(stmt);
  sqlite3_close(db);
}

static size_t get_feed_xml_write_callback(void *data, size_t size, size_t count,
                                          void *membuf) {
  size_t realsize = size * count;
  struct membuf *mem = (struct membuf *)membuf;
  mem->string = realloc(mem->string, mem->size + realsize + 1);
  memcpy(&(mem->string[mem->size]), data, realsize);
  mem->size += realsize;
  mem->string[mem->size] = 0;
  return realsize;
}

void extract_params(struct query_param **query_params, char *query_string,
                    size_t *query_params_len) {
  char *token, *key;

  while (query_string != NULL) {
    token = strsep(&query_string, "&");
    key = strsep(&token, "=");
    *query_params = realloc(*query_params, (*query_params_len + 1) *
                                               sizeof(struct query_param));
    (*query_params)[*query_params_len].key = malloc(strlen(key) + 1);
    (*query_params)[*query_params_len].val = malloc(strlen(token) + 1);
    memcpy((*query_params)[*query_params_len].key, key, strlen(key) + 1);
    memcpy((*query_params)[*query_params_len].val, token, strlen(token) + 1);

    if (query_string != NULL) {
      (*query_params_len)++;
    }
  }
}

static void handle_mongoose_event(struct mg_connection *connection, int event,
                                  void *event_data) {
  struct http_message *message = (struct http_message *)event_data;
  switch (event) {
  case MG_EV_HTTP_REQUEST:
    if (mg_vcmp(&message->uri, "/radios") == 0) {

      mg_printf(connection, "HTTP/1.1 200 OK\r\n"
                            "Transfer-Encoding: chunked\r\n\r\n");

      int radios_num = 0;
      select_radios_num(&radios_num);

      struct radio radios[radios_num];
      select_radios(radios);

      json_t *result_json_obj = json_object();
      json_t *radios_json_arr = json_array();

      int i;
      for (i = 0; i < radios_num; i++) {
        json_t *radio_json_obj = json_object();
        json_object_set_new(radio_json_obj, "name",
                            json_stringn(radios[i].name, radios[i].name_len));
        json_object_set_new(
            radio_json_obj, "stream_uri",
            json_stringn(radios[i].stream_uri, radios[i].stream_uri_len));
        json_array_append_new(radios_json_arr, radio_json_obj);
      }

      json_object_set_new(result_json_obj, "radios", radios_json_arr);

      char *result_json_str = json_dumps(result_json_obj, JSON_COMPACT);
      mg_printf_http_chunk(connection, "%s", result_json_str);
      free(result_json_str);

      mg_send_http_chunk(connection, "", 0);
    } else if (mg_vcmp(&message->uri, "/podcasts") == 0) {
      mg_printf(connection, "HTTP/1.1 200 OK\r\n"
                            "Transfer-Encoding: chunked\r\n\r\n");

      struct feed *feeds = NULL;
      int feeds_num = 0;
      select_feeds(&feeds, &feeds_num);

      json_t *result_json_obj = json_object();
      json_t *podcasts_json_arr = json_array();

      time_t time_now;
      time(&time_now);

      int i;
      for (i = 0; i < feeds_num; i++) {
        mxml_node_t *feed;
        mxml_node_t *episode;

        json_t *podcast_json_obj = json_object();
        json_t *episodes_json_arr = json_array();

        json_object_set_new(podcast_json_obj, "id", json_integer(feeds[i].id));

        struct membuf feed_xml;
        feed_xml.string = malloc(1);
        feed_xml.size = 0;

        CURL *curl_handle = NULL;
        curl_handle = curl_easy_init();
        curl_easy_setopt(curl_handle, CURLOPT_URL, feeds[i].uri);

        /* follow redirects */
        curl_easy_setopt(curl_handle, CURLOPT_FOLLOWLOCATION, 1L);

        curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION,
                         get_feed_xml_write_callback);
        curl_easy_setopt(curl_handle, CURLOPT_WRITEDATA, (void *)&feed_xml);

        curl_easy_perform(curl_handle);

        curl_easy_cleanup(curl_handle);

        /* MXML_OPAQUE_CALLBACK needs to be used, otherwise mxml will stop
         * processing the node after the first space character*/
        feed = mxmlLoadString(NULL, feed_xml.string, MXML_OPAQUE_CALLBACK);
        free(feed_xml.string);

        mxml_node_t *podcast_title = mxmlFindPath(feed, "rss/channel/title");
        json_object_set_new(podcast_json_obj, "title",
                            json_string(mxmlGetOpaque(podcast_title)));
        mxmlDelete(podcast_title);

        struct tm tm_publish;
        memset(&tm_publish, 0, sizeof(struct tm));

        for (episode =
                 mxmlFindElement(feed, feed, "item", NULL, NULL, MXML_DESCEND);
             episode != NULL;
             episode = mxmlFindElement(episode, feed, "item", NULL, NULL,
                                       MXML_DESCEND)) {
          json_t *episode_json = json_object();
          mxml_node_t *episode_detail;

          /* test if episode was published in the last 30 days, don't include
           * episode otherwise */
          episode_detail = mxmlFindPath(episode, "pubDate");
          const char *pubdate_str = mxmlGetOpaque(episode_detail);

          /*
            pubdate_str format like "Sat, 20 Aug 2016 20:54:24 +0200"
            as an alternative to strptime something like the following could be
            used:
             char month[4];
             int day, year;
             sscanf(
               pubdate_str,
               "%*s %d %s %d %*d:%*d:%*d %*s",
               &day,
               month,
               &year
             );
          */
          if (strptime(pubdate_str, "%a, %0d %b %Y %T %z", &tm_publish) !=
              NULL) {
            double time_diff = difftime(time_now, mktime(&tm_publish));
            if (time_diff / 86400.0 > 30.0) {
              break;
            }
          } else if (strptime(pubdate_str, "%a, %0d %b %Y %T %Z",
                              &tm_publish) != NULL) {
            double time_diff = difftime(time_now, mktime(&tm_publish));
            if (time_diff / 86400.0 > 30.0) {
              break;
            }
          } else {
            printf("unsupported time format: %s\n", pubdate_str);
            break;
          }

          episode_detail = mxmlFindPath(episode, "title");
          json_object_set_new(episode_json, "title",
                              json_string(mxmlGetOpaque(episode_detail)));

          episode_detail = mxmlFindPath(episode, "itunes:duration");
          json_object_set_new(episode_json, "duration",
                              json_string(mxmlGetOpaque(episode_detail)));

          episode_detail = mxmlFindPath(episode, "description");
          mxml_node_t *cdata = NULL;
          cdata = mxmlGetFirstChild(episode_detail);
          if (cdata != NULL) {
            json_object_set_new(episode_json, "description",
                                json_string(mxmlGetCDATA(cdata)));
          } else {
            json_object_set_new(episode_json, "description",
                                json_string(mxmlGetOpaque(episode_detail)));
          }
          mxmlDelete(cdata);

          episode_detail = mxmlFindPath(episode, "enclosure");
          const char *url = mxmlElementGetAttr(episode_detail, "url");
          json_object_set_new(episode_json, "stream_uri", json_string(url));

          mxmlDelete(episode_detail);

          json_array_append_new(episodes_json_arr, episode_json);
        }

        json_object_set_new(podcast_json_obj, "episodes", episodes_json_arr);
        json_array_append_new(podcasts_json_arr, podcast_json_obj);

        mxmlDelete(episode);
        mxmlDelete(feed);
      }

      json_object_set_new(result_json_obj, "podcasts", podcasts_json_arr);

      char *result_json_str = json_dumps(result_json_obj, JSON_COMPACT);
      mg_printf_http_chunk(connection, "%s", result_json_str);
      free(result_json_str);

      mg_send_http_chunk(connection, "", 0);
    } else if (mg_vcmp(&message->uri, "/podcast/episodes") == 0) {
      mg_printf(connection, "HTTP/1.1 200 OK\r\n"
                            "Transfer-Encoding: chunked\r\n\r\n");

      char *query_string =
          strndup(message->query_string.p, message->query_string.len);
      size_t query_params_len = 0;
      struct query_param *query_params = NULL;
      extract_params(&query_params, query_string, &query_params_len);
      free(query_string);

      struct feed feed;

      json_t *result_json_obj = json_object();

      mxml_node_t *feed_mxml;
      mxml_node_t *episode;

      time_t time_now;
      time(&time_now);
      double range = -1;

      json_t *podcast_json_obj = json_object();
      json_t *episodes_json_arr = json_array();

      int i;
      for (i = 0; i < query_params_len; i++) {
        if (strcmp(query_params[i].key, "id") == 0) {
          json_object_set_new(podcast_json_obj, "id",
                              json_integer(atoi(query_params[i].val)));
          select_feed(&feed, atoi(query_params[i].val));
        }
        if (strcmp(query_params[i].key, "range") == 0 &&
            strcmp(query_params[i].val, "all") != 0) {
          range = atof(query_params[i].val);
        }
      }

      struct membuf feed_xml;
      feed_xml.string = malloc(1);
      feed_xml.size = 0;

      CURL *curl_handle = NULL;
      curl_handle = curl_easy_init();
      curl_easy_setopt(curl_handle, CURLOPT_URL, feed.uri);

      /* follow redirects */
      curl_easy_setopt(curl_handle, CURLOPT_FOLLOWLOCATION, 1L);

      curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION,
                       get_feed_xml_write_callback);
      curl_easy_setopt(curl_handle, CURLOPT_WRITEDATA, (void *)&feed_xml);

      curl_easy_perform(curl_handle);

      curl_easy_cleanup(curl_handle);

      /* MXML_OPAQUE_CALLBACK needs to be used, otherwise mxml will stop
       * processing the node after the first space character*/
      feed_mxml = mxmlLoadString(NULL, feed_xml.string, MXML_OPAQUE_CALLBACK);
      free(feed_xml.string);

      mxml_node_t *podcast_title = mxmlFindPath(feed_mxml, "rss/channel/title");
      json_object_set_new(podcast_json_obj, "title",
                          json_string(mxmlGetOpaque(podcast_title)));
      mxmlDelete(podcast_title);

      struct tm tm_publish;
      memset(&tm_publish, 0, sizeof(struct tm));

      for (episode = mxmlFindElement(feed_mxml, feed_mxml, "item", NULL, NULL,
                                     MXML_DESCEND);
           episode != NULL;
           episode = mxmlFindElement(episode, feed_mxml, "item", NULL, NULL,
                                     MXML_DESCEND)) {
        json_t *episode_json = json_object();
        mxml_node_t *episode_detail;

        if (range != -1) {
          /* test if episode was published in the last range days, don't include
           * episode otherwise */
          episode_detail = mxmlFindPath(episode, "pubDate");
          const char *pubdate_str = mxmlGetOpaque(episode_detail);

          /*
            pubdate_str format like "Sat, 20 Aug 2016 20:54:24 +0200"
            as an alternative to strptime something like the following could be
            used:
             char month[4];
             int day, year;
             sscanf(
               pubdate_str,
               "%*s %d %s %d %*d:%*d:%*d %*s",
               &day,
               month,
               &year
             );
          */
          if (strptime(pubdate_str, "%a, %0d %b %Y %T %z", &tm_publish) !=
              NULL) {
            double time_diff = difftime(time_now, mktime(&tm_publish));
            if (time_diff / 86400.0 > range) {
              break;
            }
          } else if (strptime(pubdate_str, "%a, %0d %b %Y %T %Z",
                              &tm_publish) != NULL) {
            double time_diff = difftime(time_now, mktime(&tm_publish));
            if (time_diff / 86400.0 > range) {
              break;
            }
          } else {
            printf("unsupported time format: %s\n", pubdate_str);
            break;
          }
        }

        episode_detail = mxmlFindPath(episode, "title");
        json_object_set_new(episode_json, "title",
                            json_string(mxmlGetOpaque(episode_detail)));

        episode_detail = mxmlFindPath(episode, "itunes:duration");
        json_object_set_new(episode_json, "duration",
                            json_string(mxmlGetOpaque(episode_detail)));

        episode_detail = mxmlFindPath(episode, "description");
        mxml_node_t *cdata = NULL;
        cdata = mxmlGetFirstChild(episode_detail);
        if (cdata != NULL) {
          json_object_set_new(episode_json, "description",
                              json_string(mxmlGetCDATA(cdata)));
        } else {
          json_object_set_new(episode_json, "description",
                              json_string(mxmlGetOpaque(episode_detail)));
        }
        mxmlDelete(cdata);

        episode_detail = mxmlFindPath(episode, "enclosure");
        const char *url = mxmlElementGetAttr(episode_detail, "url");
        json_object_set_new(episode_json, "stream_uri", json_string(url));

        mxmlDelete(episode_detail);

        json_array_append_new(episodes_json_arr, episode_json);
      }

      json_object_set_new(podcast_json_obj, "episodes", episodes_json_arr);

      mxmlDelete(episode);
      mxmlDelete(feed_mxml);

      json_object_set_new(result_json_obj, "podcast", podcast_json_obj);

      char *result_json_str = json_dumps(result_json_obj, JSON_COMPACT);
      mg_printf_http_chunk(connection, "%s", result_json_str);
      free(result_json_str);

      mg_send_http_chunk(connection, "", 0);
    } else if (mg_vcmp(&message->uri, "/play") == 0) {
      char uri[512];
      mg_get_http_var(&message->body, "uri", uri, sizeof(uri));

      mg_printf(connection, "HTTP/1.1 200 OK\r\n"
                            "Transfer-Encoding: chunked\r\n\r\n");
      mg_send_http_chunk(connection, "", 0);

      play_audio(uri);
    } else if (mg_vcmp(&message->uri, "/pause") == 0) {
      mg_printf(connection, "HTTP/1.1 200 OK\r\n"
                            "Transfer-Encoding: chunked\r\n\r\n");
      mg_send_http_chunk(connection, "", 0);

      pause_audio();
    } else if (mg_vcmp(&message->uri, "/stop") == 0) {
      mg_printf(connection, "HTTP/1.1 200 OK\r\n"
                            "Transfer-Encoding: chunked\r\n\r\n");
      mg_send_http_chunk(connection, "", 0);

      stop_audio();
    } else {
      /* serve document root */
      mg_serve_http(connection, message, mongoose_http_server_options);
    }
    break;
  default:
    break;
  }
}

static gboolean gstreamer_bus_call(GstBus *bus, GstMessage *message,
                                   gpointer data) {
  GMainLoop *loop = (GMainLoop *)data;

  switch (GST_MESSAGE_TYPE(message)) {
  case GST_MESSAGE_EOS:
    g_main_loop_quit(loop);
    break;
  case GST_MESSAGE_ERROR: {
    gchar *debug;
    GError *error;

    gst_message_parse_error(message, &error, &debug);
    g_free(debug);
    g_printerr(error->message);
    g_error_free(error);

    g_main_loop_quit(loop);
    break;
  }
  default:
    break;
  }

  return TRUE;
}

void play_audio(char *uri) {
  GstBus *bus;

  /* do not init with option; usually &arg and &argv would be used here */
  gst_init(NULL, NULL);

  /* parameters are
     GMainContext *context (if NULL, the default context will be used),
     gboolean is_running (set to TRUE to indicate that the loop is running.
     This is not very important since calling g_main_loop_run() will set this
     to TRUE anyway)*/
  loop = g_main_loop_new(NULL, FALSE);

  pipeline = gst_element_factory_make("playbin", "player");

  /* enable to pass in uris like file://, http://, etc. */
  g_object_set(G_OBJECT(pipeline), "uri", uri, NULL);

  bus = gst_pipeline_get_bus(GST_PIPELINE(pipeline));
  gst_bus_add_watch(bus, gstreamer_bus_call, loop);
  gst_object_unref(bus);

  gst_element_set_state(GST_ELEMENT(pipeline), GST_STATE_PLAYING);
  playing = 1;
  g_main_loop_run(loop);

  gst_element_set_state(GST_ELEMENT(pipeline), GST_STATE_NULL);
  gst_object_unref(GST_OBJECT(pipeline));
}

void pause_audio() {
  if (playing) {
    gst_element_set_state(GST_ELEMENT(pipeline), GST_STATE_PAUSED);
    playing = 0;
  } else {
    gst_element_set_state(GST_ELEMENT(pipeline), GST_STATE_PLAYING);
    playing = 1;
  }
}

void stop_audio() { g_main_loop_quit(loop); }

int main(int argc, char **argv) {
  if (strcmp("-i", argv[1]) == 0) {
    CURL *curl_handle = NULL;
    struct curl_slist *request_headers = NULL;

    /* set icy metadata request header to receive icy-metaint in the response
     * headers */
    request_headers = curl_slist_append(request_headers, "Icy-MetaData:1");

    curl_handle = curl_easy_init();

    /* set request headers */
    curl_easy_setopt(curl_handle, CURLOPT_HTTPHEADER, request_headers);

    /* set url */
    curl_easy_setopt(curl_handle, CURLOPT_URL, argv[2]);

    /* follow redirects */
    curl_easy_setopt(curl_handle, CURLOPT_FOLLOWLOCATION, 1L);

    /* set response header callback */
    curl_easy_setopt(curl_handle, CURLOPT_HEADERFUNCTION,
                     icy_meta_header_callback);

    /* set response body callback */
    curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION,
                     icy_meta_write_callback);

    /* make request */
    curl_easy_perform(curl_handle);

    /* cleanup curl stuff */
    curl_slist_free_all(request_headers);
    curl_easy_cleanup(curl_handle);
  } else if (strcmp("-s", argv[1]) == 0) {
    struct mg_mgr mongoose_event_manager;
    struct mg_connection *mongoose_connection;

    mg_mgr_init(&mongoose_event_manager, NULL);
    mongoose_connection =
        mg_bind(&mongoose_event_manager, "8080", handle_mongoose_event);
    mg_set_protocol_http_websocket(mongoose_connection);
    mg_enable_multithreading(mongoose_connection);
    mongoose_http_server_options.document_root = "./stc";

    while (1) {
      mg_mgr_poll(&mongoose_event_manager, 1000);
    }

    mg_mgr_free(&mongoose_event_manager);
  } else {
    play_audio(argv[1]);
  }

  return 0;
}
