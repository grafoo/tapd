#! /usr/bin/env python2

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import gi; gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
import json
import sqlite3
import os
import urllib2
from xml.etree import ElementTree
import threading
import Queue


class Gstreamer(object):
    def __init__(self, player=Gst.Element, loop=GLib.MainLoop, queue=Queue.Queue):
        self.player = player
        self.loop = loop
        self.bus = Gst.Bus
        self.queue = queue

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


class TapdHandler(BaseHTTPRequestHandler):
    mediatypes = {
        'html': 'text/html',
        'css': 'text/css',
        'js': 'application/javascript',
        'svg': 'image/svg+xml'
    }

    gstreamer = Gstreamer

    def get_rss_xml(self, queue, podcast_id, uri):
        try:
            request = urllib2.Request(uri, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'})
            xmlroot = ElementTree.fromstring(urllib2.urlopen(request).read())
            podcast = {'id': podcast_id, 'title': xmlroot.find('channel/title').text, 'episodes': []}
            for item in xmlroot.findall('channel/item'):
                episode = {'title': item.find('title').text}
                episode['description'] = item.find('description').text
                episode['stream_uri'] = item.find('enclosure').get('url')
                episode['duration'] = item.find('{http://www.itunes.com/dtds/podcast-1.0.dtd}duration').text
                podcast['episodes'].append(episode)
            queue.put(podcast)
        except Exception as e:
            print threading.current_thread(), e, uri


    def do_GET(self):
        if self.path == '/':
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
            response = {'radios': [{'name': name, 'stream_uri': uri} for name, uri in cursor.execute('select name, stream_uri from radios')]}
            db.close()
            self.wfile.write(json.dumps(response))
        elif self.path == '/podcasts':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            db = sqlite3.connect('tapd.db')
            cursor = db.cursor()

            podcasts = []

            queue = Queue.Queue()

            threads = []
            for podcast_id, uri in cursor.execute('select id, uri from feeds'):
                thread = threading.Thread(target=self.get_rss_xml, args=(queue, podcast_id, uri,))
                threads.append(thread)
                thread.start()

            [thread.join() for thread in threads]

            while not queue.empty():
                podcasts.append(queue.get())

            db.close()

            self.wfile.write(json.dumps({'podcasts': podcasts}))
        elif self.path == '/stop':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.gstreamer.player.set_state(Gst.State.NULL)
            self.wfile.write('stopped.')
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
            self.wfile.write('')
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
            self.wfile.write('')
        elif self.path == '/pause':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            if self.gstreamer.player.get_state(Gst.CLOCK_TIME_NONE)[1] == Gst.State.PLAYING:
                self.gstreamer.player.set_state(Gst.State.PAUSED)
            elif self.gstreamer.player.get_state(Gst.CLOCK_TIME_NONE)[1] == Gst.State.PAUSED:
                self.gstreamer.player.set_state(Gst.State.PLAYING)
            self.wfile.write('')
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
            uri = self.rfile.read(int(self.headers.getheader('Content-Length'))).split('=')[1]
            self.wfile.write('')
            self.gstreamer.player.set_property('uri', uri)
            self.gstreamer.player.set_state(Gst.State.PLAYING)


def run_httpserver(server):
    try:
        httpServer.serve_forever()
    except:
        pass


if __name__ == '__main__':
    try:
        with open('tapd.pid', 'w') as pid_file:
            pid_file.write(str(os.getpid()) + os.linesep)

        GObject.threads_init()
        Gst.init(None)
        loop = GLib.MainLoop()
        player = Gst.ElementFactory.make('playbin', None)
        queue = Queue.Queue()
        gstreamer = Gstreamer(player, loop, queue)
        threading.Thread(target=gstreamer).start()

        tapdHandler = TapdHandler
        tapdHandler.gstreamer = gstreamer

        httpServer = HTTPServer(('', 8000), tapdHandler)
        threading.Thread(target=run_httpserver, args=(httpServer,)).start()

        while queue.empty():
            pass

        raise queue.get()
    except KeyboardInterrupt:
        print('')
    finally:
        loop.quit()
        httpServer.socket.close()
