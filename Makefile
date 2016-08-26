OS_DEBIAN_JESSIE := $(shell grep "^8" /etc/debian_version 2>/dev/null)

all:
ifeq ($(OS_DEBIAN_JESSIE),)
	$(CC) -Wall -otapd src/tapd.c src/mongoose/mongoose.c -DMG_ENABLE_THREADS -lpthread -lcurl $(shell pkg-config --cflags --libs gstreamer-1.0) -ljansson -lsqlite3 -lmxml
else
	$(CC) -Wall -otapd src/tapd.c src/mongoose/mongoose.c -DMG_ENABLE_THREADS -DOS_DEBIAN_JESSIE -L dep/lib -lpthread -lcurl $(shell pkg-config --cflags --libs gstreamer-1.0) -ljansson -lsqlite3 -lmxml
endif

clean:
	rm tapd
