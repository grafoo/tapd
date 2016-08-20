all:
	cc -o tapd src/tapd.c src/mongoose/mongoose.c -D MG_ENABLE_THREADS -l pthread -l curl $(shell pkg-config --cflags --libs gstreamer-1.0) -l jansson -l sqlite3 -l mxml

clean:
	rm tapd
