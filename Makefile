all:
	cc -Wall -otapd src/tapd.c src/mongoose/mongoose.c -DMG_ENABLE_THREADS -lpthread -lcurl $(shell pkg-config --cflags --libs gstreamer-1.0) -ljansson -lsqlite3 -lmxml

clean:
	rm tapd
