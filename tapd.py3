#! /usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import gi; gi.require_version('Gst', '1.0')
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
            self.bus = player.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect('message', self.gstreamer_bus_callback)
            self.loop.run()
        except KeyboardInterrupt as e:
            self.queue.put(e)

    def gstreamer_bus_callback(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.NULL)
            self.stream_uri = ''
            self.radio_id = 0


class TapdHandler(BaseHTTPRequestHandler):
    mediatypes = {
        'html': 'text/html',
        'css': 'text/css',
        'js': 'application/javascript',
        'svg': 'image/svg+xml'
    }

    gstreamer = Gstreamer

    def get_episode(self, item):
        episode = {'title': item.find('title').text}

        description = item.find('description')
        if description: episode['description'] = description.text

        stream_uri = item.find('enclosure').get('url')
        if stream_uri: episode['stream_uri'] = stream_uri

        duration = item.find('{http://www.itunes.com/dtds/podcast-1.0.dtd}duration')
        if duration: episode['duration'] = duration.text

        content = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
        if content: episode['content'] = content.text

        return episode

    def get_rss_xml(self, queue, podcast_id, uri, all=False):
        try:
            request = urllib.request.Request(uri, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'})
            xmlroot = ElementTree.fromstring(urllib.request.urlopen(request).read())
            podcast = {'id': podcast_id, 'title': xmlroot.find('channel/title').text, 'episodes': []}
            for item in xmlroot.findall('channel/item'):
                if all:
                    podcast['episodes'].append(self.get_episode(item))
                else:
                    pubdate_notz = ' '.join(item.find('pubDate').text.split(' ')[:-1])
                    pubdate_diff_now = time.time() - time.mktime(time.strptime(pubdate_notz, '%a, %d %b %Y %X'))
                    if pubdate_diff_now / 86400.0 < 30.0:
                        podcast['episodes'].append(self.get_episode(item))
            queue.put(podcast)
        except: pass

    def poll_icy_metadata(self, protocol='http', host='', port=80, url='', queue=Queue):
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

    def get_icy_metadata(self, protocol='http', host='', port=80, url='', queue=Queue):
        try:
            connection = client.HTTPConnection(host, port=port)
            connection.request('GET', url, headers={'Icy-MetaData': 1})
            response = connection.getresponse()
            headers = dict(response.getheaders())
            if 'icy-metaint' in headers.keys():
                metaint = int(headers['icy-metaint'])
                pattern = re.compile(r"StreamTitle='(.+)';")
                metalen = response.read(metaint + 1)[-1]
                if metalen > 0:
                    metadata = response.read(metalen * 16).decode('utf-8')
                    match = pattern.match(metadata)
                    if match:
                        stream_title = match.group(1)
                        queue.put(stream_title)
            else:
                queue.put('no icy metadata')
        except Exception as e:
            print('getting metadata for {0} failed with {1}'.format(host, e))
            queue.put('no icy metadata')
        finally:
            connection.close()

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
            response = {'radios': [{'id': id, 'name': name} for id, name in cursor.execute('select id, name from radios')]}
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
                thread = threading.Thread(target=self.get_rss_xml, args=(fetcher_queue, podcast_id, uri,))
                threads.append(thread)
                thread.start()

            for thread in threads: thread.join()

            while not fetcher_queue.empty():
                podcasts.append(fetcher_queue.get())

            db.close()

            self.wfile.write(json.dumps({'podcasts': podcasts}).encode('UTF-8'))
        elif path_parsed.path.split('/')[1] == 'podcast':
            if path_parsed.path.split('/')[2] == 'episodes':
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                db = sqlite3.connect('tapd.db')
                cursor = db.cursor()
                cursor.execute('select uri from feeds where id=?', query['id'])
                uri = cursor.fetchone()[0]
                queue = Queue()
                thread = threading.Thread(target=self.get_rss_xml, args=(queue, query['id'], uri, True))
                thread.start()
                thread.join()
                podcast = queue.get()
                db.close()
                self.wfile.write(json.dumps({'podcast': podcast}).encode('UTF-8'))
        elif self.path == '/stop':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.gstreamer.player.set_state(Gst.State.NULL)
            self.gstreamer.stream_uri = ''
            self.gstreamer.radio_id = 0
            self.wfile.write('stopped.'.encode('UTF-8'))
        elif self.path == '/forward':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            current_position = self.gstreamer.player.query_position(Gst.Format.TIME)
            duration = self.gstreamer.player.query_duration(Gst.Format.TIME)
            if current_position[0] and duration[0]:
                new_position = current_position[1] + 30 * Gst.SECOND
                if new_position < duration:
                    self.gstreamer.player.seek_simple(Gst.Format.TIME,
                                                      Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                                                      new_position)
            self.wfile.write(''.encode('UTF-8'))
        elif self.path == '/backward':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            current_position = self.gstreamer.player.query_position(Gst.Format.TIME)
            if current_position[0]:
                new_position = current_position[1] - 30 * Gst.SECOND
                if new_position < 0:
                    new_position = 0
                self.gstreamer.player.seek_simple(Gst.Format.TIME,
                                                  Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                                                  new_position)
            self.wfile.write(''.encode('UTF-8'))
        elif self.path == '/pause':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            if self.gstreamer.player.get_state(Gst.CLOCK_TIME_NONE)[1] == Gst.State.PLAYING:
                self.gstreamer.player.set_state(Gst.State.PAUSED)
            elif self.gstreamer.player.get_state(Gst.CLOCK_TIME_NONE)[1] == Gst.State.PAUSED:
                self.gstreamer.player.set_state(Gst.State.PLAYING)
            self.wfile.write(''.encode('UTF-8'))
        elif self.path == '/streaminfo':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if self.gstreamer.radio_id > 0:
                db = sqlite3.connect('tapd.db')
                cursor = db.cursor()
                protocol, host, port, url = cursor.execute(
                    'select stream_protocol, stream_host, stream_port, stream_url from radios where id = ?',
                    (self.gstreamer.radio_id,)
                ).fetchone()
                db.close()
                fetcher_queue = Queue()
                thread = threading.Thread(target=self.get_icy_metadata, args=(protocol, host, port, url, fetcher_queue,))
                thread.start()
                thread.join()
                streaminfo = {'title': fetcher_queue.get()}
                self.wfile.write(json.dumps(streaminfo).encode('UTF-8'))
            else:
                streaminfo = {'title': self.gstreamer.stream_uri}
                self.wfile.write(json.dumps(streaminfo).encode('UTF-8'))
        else:
            try:
                mediatype = self.path.split('.')
                if len(mediatype) > 1:
                    if mediatype[-1] in self.mediatypes:
                        self.send_response(200)
                        self.send_header('Content-Type', self.mediatypes[mediatype[-1]])
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
            uri = self.rfile.read(int(self.headers.get('Content-Length'))).decode('UTF-8').split('=')[1]
            self.wfile.write(''.encode('UTF-8'))
            self.gstreamer.player.set_property('uri', uri)
            self.gstreamer.player.set_state(Gst.State.PLAYING)
            self.gstreamer.stream_uri = uri
        elif self.path == '/playradio':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            radio_id = int(self.rfile.read(int(self.headers.get('Content-Length'))).decode('UTF-8').split('=')[1])
            self.wfile.write(''.encode('UTF-8'))
            db = sqlite3.connect('tapd.db')
            cursor = db.cursor()
            protocol, host, port, url = cursor.execute(
                'select stream_protocol, stream_host, stream_port, stream_url from radios where id = ?',
                (radio_id,)
            ).fetchone()
            db.close()
            self.gstreamer.player.set_property('uri', '{0}://{1}:{2}{3}'.format(protocol, host, port,url))
            self.gstreamer.player.set_state(Gst.State.PLAYING)
            self.gstreamer.radio_id = radio_id

    def log_message(self, format, *args): pass


def run_httpserver(server):
    try: httpServer.serve_forever()
    except: pass


if __name__ == '__main__':
    try:
        with open('tapd.pid', 'w') as pid_file:
            pid_file.write(str(os.getpid()) + os.linesep)

        GObject.threads_init()
        Gst.init(None)
        loop = GLib.MainLoop()
        player = Gst.ElementFactory.make('playbin', None)
        queue = Queue()
        gstreamer = Gstreamer(player, loop, queue)
        threading.Thread(target=gstreamer).start()

        tapdHandler = TapdHandler
        tapdHandler.gstreamer = gstreamer

        httpServer = HTTPServer(('', 8000), tapdHandler)
        threading.Thread(target=run_httpserver, args=(httpServer,)).start()

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

