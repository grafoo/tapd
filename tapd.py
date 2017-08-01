#! /usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from gi import require_version
require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
import json
import sqlite3
import os
import urllib.request, urllib.error, urllib.parse
from xml.etree import ElementTree
import threading
from queue import Queue
import time
import urllib.parse
from http import client
import re
from socketserver import ThreadingMixIn
import base64
from hashlib import sha1


class Gstreamer(object):
    def __init__(self, player=Gst.Element, loop=GLib.MainLoop, queue=Queue):
        self.player = player
        self.loop = loop
        self.bus = Gst.Bus
        self.queue = queue
        self.stream_uri = ''
        self.radio_id = 0

    def __call__(self, *args, **kwargs):
        try:
            self.bus = self.player.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect('message', self.gstreamer_bus_callback)
            self.loop.run()
        except KeyboardInterrupt as e:
            self.queue.put(e)

    def gstreamer_bus_callback(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.NULL)
            self.remove_stream_position()
            self.stream_uri = ''
            self.radio_id = 0

    def remove_stream_position(self):
        db = sqlite3.connect('tapd.db')
        cursor = db.cursor()
        try:
            cursor.execute('update episodes set position = NULL where url = ?',
                           (self.stream_uri, ))
            db.commit()
        except Exception as err:
            print(err)
        finally:
            db.close()


class TapdHandler(BaseHTTPRequestHandler):
    mediatypes = {
        'html': 'text/html',
        'css': 'text/css',
        'js': 'application/javascript',
        'svg': 'image/svg+xml'
    }

    gstreamer = Gstreamer

    def get_episode(self, item):
        try:
            episode = {'title': item.find('title').text}

            description = item.find('description')
            if description is not None:
                episode['description'] = description.text
            else:
                episode['description'] = None

            stream_uri = item.find('enclosure').get('url')
            episode['stream_uri'] = stream_uri if stream_uri else None

            duration = item.find(
                '{http://www.itunes.com/dtds/podcast-1.0.dtd}duration')
            if duration is not None:
                episode['duration'] = duration.text
            else:
                episode['duration'] = None

            content = item.find(
                '{http://purl.org/rss/1.0/modules/content/}encoded')
            if content is not None:
                episode['content'] = content.text
            else:
                episode['content'] = None
            return episode
        except Exception as err:
            print(err)

    def get_rss_xml(self, queue, podcast_id, uri, all=False):
        try:
            request = urllib.request.Request(
                uri,
                headers={
                    'User-Agent':
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
                })
            xmlroot = ElementTree.fromstring(
                urllib.request.urlopen(request).read())
            podcast = {
                'id': podcast_id,
                'title': xmlroot.find('channel/title').text,
                'episodes': []
            }
            for item in xmlroot.findall('channel/item'):
                if all:
                    podcast['episodes'].append(self.get_episode(item))
                else:
                    pubdate_notz = ' '.join(
                        item.find('pubDate').text.split(' ')[:-1])
                    pubdate_diff_now = time.time() - time.mktime(
                        time.strptime(pubdate_notz, '%a, %d %b %Y %X'))
                    if pubdate_diff_now / 86400.0 < 30.0:
                        podcast['episodes'].append(self.get_episode(item))
            queue.put(podcast)
        except:
            pass

    def poll_icy_metadata(self,
                          protocol='http',
                          host='',
                          port=80,
                          url='',
                          queue=Queue):
        # todo: run this as a permanent thread when radio is playing
        try:
            connection = client.HTTPConnection(host, port=port)
            connection.request('GET', url, headers={'Icy-MetaData': 1})
            response = connection.getresponse()
            metaint = int(dict(response.getheaders())['icy-metaint'])
            pattern = re.compile(r"StreamTitle='(.+)';")
            while True:
                metalen = response.read(metaint + 1)[-1]
                if metalen > 0:
                    metadata = response.read(metalen * 16).decode('utf-8')
                    match = pattern.match(metadata)
                    if match:
                        stream_title = match.group(1)
                        queue.put(stream_title)
        except:
            pass
        finally:
            connection.close()

    def get_icy_metadata(self,
                         protocol='http',
                         host='',
                         port=80,
                         url='',
                         queue=Queue):
        try:
            connection = client.HTTPConnection(host, port=port)
            connection.request('GET', url, headers={'Icy-MetaData': 1})
            response = connection.getresponse()
            headers = dict(response.getheaders())
            if 'icy-metaint' in headers.keys():
                metaint = int(headers['icy-metaint'])
                metalen = response.read(metaint + 1)[-1]
                if metalen > 0:
                    # metadata looks like StreamTitle='<some title>';StreamUrl='<some url>';
                    metadata = response.read(metalen * 16).decode('utf-8')
                    result = {}
                    for part in metadata.split(';'):
                        if len(part) != len(part.split('\x00')) - 1:
                            key, val = part.split('=')
                            if key == 'StreamTitle':
                                key = 'title'
                                result['title'] = val[1:-1].strip()
                            elif key == 'StreamUrl':
                                result['url'] = val[1:-1].strip()
                    queue.put(result)
            else:
                queue.put('no icy metadata')
        except Exception as e:
            print('getting metadata for {0} failed with {1}'.format(host, e))
            queue.put('no icy metadata')
        finally:
            connection.close()

    def get_streaminfo(self):
        if self.gstreamer.radio_id > 0:
            db = sqlite3.connect('tapd.db')
            cursor = db.cursor()
            protocol, host, port, url = cursor.execute(
                'select stream_protocol, stream_host, stream_port, stream_url from radios where id = ?',
                (self.gstreamer.radio_id, )).fetchone()
            db.close()
            fetcher_queue = Queue()
            thread = threading.Thread(
                target=self.get_icy_metadata,
                args=(protocol, host, port, url, fetcher_queue, ))
            thread.start()
            thread.join()
            return fetcher_queue.get()
        else:
            return {'title': self.gstreamer.stream_uri}

    def do_GET(self):
        path_parsed = urllib.parse.urlparse(self.path)
        if path_parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open('stc/index.html', 'rb') as f:
                self.wfile.write(f.read())
        elif self.path == '/radios':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            db = sqlite3.connect('tapd.db')
            cursor = db.cursor()
            response = {
                'radios':
                [{
                    'id': id,
                    'name': name
                }
                 for id, name in cursor.execute('select id, name from radios')]
            }
            db.close()
            self.wfile.write(json.dumps(response).encode('UTF-8'))
        elif self.path == '/podcasts':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            db = sqlite3.connect('tapd.db')
            cursor = db.cursor()

            podcasts = []

            fetcher_queue = Queue()

            threads = []
            for podcast_id, uri in cursor.execute('select id, uri from feeds'):
                thread = threading.Thread(
                    target=self.get_rss_xml,
                    args=(fetcher_queue, podcast_id, uri, ))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            while not fetcher_queue.empty():
                podcasts.append(fetcher_queue.get())

            db.close()

            self.wfile.write(
                json.dumps({
                    'podcasts': podcasts
                }).encode('UTF-8'))
        elif path_parsed.path.split('/')[1] == 'podcast':
            if path_parsed.path.split('/')[2] == 'episodes':
                query = urllib.parse.parse_qs(
                    urllib.parse.urlparse(self.path).query)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                db = sqlite3.connect('tapd.db')
                cursor = db.cursor()
                cursor.execute('select uri from feeds where id=?', query['id'])
                uri = cursor.fetchone()[0]
                queue = Queue()
                thread = threading.Thread(
                    target=self.get_rss_xml,
                    args=(queue, query['id'], uri, True))
                thread.start()
                thread.join()
                podcast = queue.get()
                for episode in podcast['episodes']:
                    try:
                        cursor.execute(
                            'select id from episodes where url=quote(?)', (
                                episode['stream_uri'], ))
                        if not cursor.fetchone():
                            cursor.execute(
                                'insert into episodes(url) values(?)', (
                                    episode['stream_uri'], ))
                            id_ = cursor.execute(
                                'select last_insert_rowid()').fetchone()[0]
                            cursor.execute(
                                'insert into episode_search values(?, ?, ?)',
                                (id_, episode['description'],
                                 episode['content'], ))
                            db.commit()
                        # url = re.sub(r'[^a-zA-Z0-9]+', ' ', episode['stream_uri'])
                    except Exception as err:
                        if type(err) is not sqlite3.IntegrityError:
                            print('[ERROR]', type(err), err)
                db.close()
                self.wfile.write(
                    json.dumps({
                        'podcast': podcast
                    }).encode('UTF-8'))
        elif self.path == '/stop':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.gstreamer.player.set_state(Gst.State.NULL)
            self.gstreamer.remove_stream_position()
            self.gstreamer.stream_uri = ''
            self.gstreamer.radio_id = 0
            self.wfile.write('stopped.'.encode('UTF-8'))
        elif self.path == '/forward':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            current_position = self.gstreamer.player.query_position(
                Gst.Format.TIME)
            duration = self.gstreamer.player.query_duration(Gst.Format.TIME)
            if current_position[0] and duration[0]:
                new_position = current_position[1] + 30 * Gst.SECOND
                if new_position < duration[1]:
                    self.gstreamer.player.seek_simple(
                        Gst.Format.TIME,
                        Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                        new_position)
            self.wfile.write(''.encode('UTF-8'))
        elif self.path == '/backward':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            current_position = self.gstreamer.player.query_position(
                Gst.Format.TIME)
            if current_position[0]:
                new_position = current_position[1] - 30 * Gst.SECOND
                if new_position < 0:
                    new_position = 0
                self.gstreamer.player.seek_simple(
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, new_position)
            self.wfile.write(''.encode('UTF-8'))
        elif self.path.startswith('/seek/'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            time_str = urllib.parse.unquote(self.path.split('/')[2])
            minutes, seconds = time_str.split(':')
            position = (int(minutes) * 60 + int(seconds)) * Gst.SECOND
            playing, _ = self.gstreamer.player.query_position(Gst.Format.TIME)
            if playing:
                self.gstreamer.player.seek_simple(
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, position)
            self.wfile.write(''.encode('UTF-8'))
        elif self.path == '/pause':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            # get_state is a blocking call
            # with Gst.CLOCK_TIME_NONE the call will not timeout
            # todo: change this to timeout and add error handling
            # get_state returns a _ResultTuple like
            #     (<enum GST_STATE_CHANGE_SUCCESS of type Gst.StateChangeReturn>,
            #      state=<enum GST_STATE_PLAYING of type Gst.State>,
            #      pending=<enum GST_STATE_VOID_PENDING of type Gst.State>)
            # when the state is playing or
            #     (<enum GST_STATE_CHANGE_SUCCESS of type Gst.StateChangeReturn>,
            #      state=<enum GST_STATE_PAUSED of type Gst.State>,
            #      pending=<enum GST_STATE_VOID_PENDING of type Gst.State>)
            # when the sate is paused.

            _, state, _ = self.gstreamer.player.get_state(Gst.CLOCK_TIME_NONE)
            db = sqlite3.connect('tapd.db')
            if state == Gst.State.PLAYING:
                self.gstreamer.player.set_state(Gst.State.PAUSED)
                _, position = self.gstreamer.player.query_position(
                    Gst.Format.TIME)
                cursor = db.cursor()
                cursor.execute(
                    'update episodes set position = ? where url = ?', (
                        position, self.gstreamer.stream_uri, ))
                db.commit()
            db.close()
            self.wfile.write(''.encode('UTF-8'))
        elif self.path == '/streaminfo':
            # todo: send current stream position to client (format mm:ss)
            # playing, position = self.gstreamer.player.query_position(
            #     Gst.Format.TIME)
            # minutes, seconds = divmod(position / Gst.SECOND, 60)

            sec_websocket_key = self.headers.get('Sec-WebSocket-Key')
            if sec_websocket_key is not None:
                websocket_magic_string = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
                hash = sha1()
                foo = '{0}{1}'.format(sec_websocket_key,
                                      websocket_magic_string)
                hash.update(bytes(foo.encode('UTF-8')))
                sec_websocket_accept = base64.b64encode(hash.digest())
                self.send_response(101)
                self.send_header('Upgrade', 'websocket')
                self.send_header('Connection', 'Upgrade')
                self.send_header('Sec-WebSocket-Accept',
                                 sec_websocket_accept.decode('UTF-8'))
                self.end_headers()
                streaminfo = ''
                while True:
                    streaminfo_new = json.dumps(self.get_streaminfo())
                    if streaminfo != streaminfo_new:
                        streaminfo = streaminfo_new
                        frame = bytearray()
                        # todo: add handling payloads with greater length than 125

                        # see https://tools.ietf.org/html/rfc6455#page-28 for details on the frame

                        # bits from left to right (which make up the first byte):
                        #   - FIN: 1 bit
                        #   - RSV1, RSV2, RSV3: 1 bit each
                        #   - Opcode: 4 bits (the 0x1 in this case denotes a text frame)
                        frame.append(0b10000001)

                        # another byte is made up from (also left to right):
                        #   - Mask: 1 bit
                        #   - Payload length: 7 bits (when payload length < 125)
                        frame.append(len(streaminfo))

                        #   ... some parts of the frame have been left out here because they are not needed

                        #   - Application data (the remaining part of the frame)
                        frame.extend(bytearray(streaminfo.encode('utf-8')))
                        self.wfile.write(frame)
                    time.sleep(1)
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(
                    json.dumps(self.get_streaminfo()).encode('UTF-8'))
        elif self.path.startswith('/search/'):
            query = urllib.parse.unquote(self.path.split('/')[2])
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            db = sqlite3.connect('tapd.db')
            cursor = db.cursor()
            cursor.execute(
                'select id from episode_search where episode_search match ?', (
                    query, ))
            result = '<!DOCTYPE html><body><html>'
            for id in (id[0] for id in cursor.fetchall()):
                cursor.execute('select url from episodes where id=?', (id, ))
                url = cursor.fetchone()[0]
                result += '%s\n' % url
            db.close()
            result += '</body></html>'
            self.wfile.write(result.encode('UTF-8'))
        else:
            try:
                mediatype = self.path.split('.')
                if len(mediatype) > 1:
                    if mediatype[-1] in self.mediatypes:
                        self.send_response(200)
                        self.send_header('Content-Type',
                                         self.mediatypes[mediatype[-1]])
                        self.end_headers()
                        with open('stc' + self.path, 'rb') as f:
                            self.wfile.write(f.read())
            except Exception as e:
                print(e)

    def do_POST(self):
        if self.path == '/play':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            uri = self.rfile.read(int(self.headers.get(
                'Content-Length'))).decode('UTF-8').split('=')[1]
            self.wfile.write(''.encode('UTF-8'))
            if self.gstreamer.player.get_property('current-uri') != uri:
                position = None
                try:
                    db = sqlite3.connect('tapd.db')
                    cursor = db.cursor()
                    cursor.execute('insert into episodes(url) values(?)',
                                   (uri, ))
                    db.commit()
                except sqlite3.IntegrityError as err:
                    cursor.execute(
                        'select position from episodes where url = ?', (uri, ))
                    position = cursor.fetchone()[0]
                finally:
                    db.close()
                self.gstreamer.player.set_state(Gst.State.NULL)
                self.gstreamer.player.set_property('uri', uri)
                self.gstreamer.player.set_state(Gst.State.PLAYING)
                if position:
                    time.sleep(
                        0.6
                    )  # 0.1 is enough for a `i5 M 580` but `ARM Cortex-A7` seems to need 0.6
                    done = self.gstreamer.player.seek_simple(
                        Gst.Format.TIME,
                        Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, position)
                    if not done:
                        print('seek from paused position failed.')
                self.gstreamer.stream_uri = uri

        elif self.path == '/playradio':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            radio_id = int(
                self.rfile.read(int(self.headers.get('Content-Length')))
                .decode('UTF-8').split('=')[1])
            self.wfile.write(''.encode('UTF-8'))
            db = sqlite3.connect('tapd.db')
            cursor = db.cursor()
            protocol, host, port, url = cursor.execute(
                'select stream_protocol, stream_host, stream_port, stream_url from radios where id = ?',
                (radio_id, )).fetchone()
            db.close()
            uri = '{0}://{1}:{2}{3}'.format(protocol, host, port, url)
            if self.gstreamer.player.get_property('current-uri') != uri:
                self.gstreamer.player.set_state(Gst.State.NULL)
                self.gstreamer.player.set_property('uri', uri)
                self.gstreamer.player.set_state(Gst.State.PLAYING)
                self.gstreamer.radio_id = radio_id

    def log_message(self, format, *args):
        pass


def run_httpserver(server):
    server.serve_forever()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """threads ftw!"""


def main():
    try:
        with open('tapd.pid', 'w') as pid_file:
            pid_file.write(str(os.getpid()) + os.linesep)

        GObject.threads_init()
        Gst.init(None)
        loop = GLib.MainLoop()
        player = Gst.ElementFactory.make('playbin', None)
        player.set_property('audio-sink',
                            Gst.ElementFactory.make('pulsesink', None))
        queue = Queue()
        gstreamer = Gstreamer(player, loop, queue)
        threading.Thread(target=gstreamer).start()

        tapdHandler = TapdHandler
        tapdHandler.gstreamer = gstreamer

        httpServer = ThreadedHTTPServer(('localhost', 8000), tapdHandler)
        httpServer.daemon_threads = True
        threading.Thread(target=run_httpserver, args=(httpServer, )).start()

        while queue.empty():
            time.sleep(1)

        raise queue.get()
    except KeyboardInterrupt:
        httpServer.shutdown()
        print(' sigint killed the radio star...')
    except Exception as e:
        print(e)
    finally:
        loop.quit()
        httpServer.socket.close()


if __name__ == '__main__':
    main()
