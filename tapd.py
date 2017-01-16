#! /usr/bin/env python2

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import gi; gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
import json
import sqlite3
import sys
import threading
import os


def gstreamer_bus_callback(bus, message):
    if message.type == Gst.MessageType.EOS:
        pass

def gstreamer_run(player, loop):
    bus = player.get_bus()
    bus.add_signal_watch()
    bus.connect('message', gstreamer_bus_callback)
    loop.run()

class TapdHandler(BaseHTTPRequestHandler):
    mediatypes = {
        'html': 'text/html',
        'css': 'text/css',
        'js': 'application/javascript',
        'svg': 'image/svg+xml'
    }

    player = Gst.Element

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
        elif self.path == '/stop':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.player.set_state(Gst.State.NULL)
            self.wfile.write("stopped.")
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
            self.wfile.write('foo')
            self.player.set_property('uri', uri)
            self.player.set_state(Gst.State.PLAYING)


if __name__ == '__main__':
    try:
        with open('tapd.pid', 'w') as pid_file:
            pid_file.write(str(os.getpid()) + os.linesep)

        GObject.threads_init()
        Gst.init(None)
        loop = GLib.MainLoop()
        player = Gst.ElementFactory.make('playbin', None)
        threading.Thread(target=gstreamer_run, args=(player, loop,)).start()

        tapdHandler = TapdHandler
        tapdHandler.player = player


        httpServer = HTTPServer(('', 8080), tapdHandler)
        httpServer.serve_forever()
    except KeyboardInterrupt as e:
        pass
    finally:
        loop.quit()
        httpServer.socket.close()
