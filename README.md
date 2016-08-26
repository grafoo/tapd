#tapd
the tiny audio player daemon - /o'zapft is/

#dependencies

## debian
```
sudo apt-get install \
  gcc \
  gstreamer1.0-alsa \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-ugly \
  libao-dev \
  libcurl4-nss-dev \
  libgstreamer1.0-dev \
  libjansson-dev \
  libmpg123-dev \
  libmxml-dev \
  libsqlite3-dev \
  make \
  sqlite3
```

### jessie
debian jessie is using mxml 2.6 where the api differes quite a lot.
therefore mxml needs to be built from sources which are available at http://www.msweet.org/files/project3/mxml-2.10.tar.gz

## opensuse
```
sudo zypper addrepo http://download.opensuse.org/repositories/devel:/libraries:/c_c++/openSUSE_Factory/devel:libraries:c_c++.repo # needed for libmrss
sudo zypper refresh
sudo zypper install \
  alsa-devel \
  gcc \
  gstreamer-devel \
  libao-devel \
  libjansson-devel \
  libmrss-devel \
  make \
  mxml-devel \
  scons # makes it easier to include non package mpg123 \
  sqlite3 # for interacting with the database \
  sqlite3-devel
```

it seems that there is no standard package for mpg123, so this needs to be built manually.
the sources can be found on e.g. https://www.mpg123.de/download/mpg123-1.23.6.tar.bz2

configure the makefile accordingly to install all targets to the dep directory of this repo.

after building mpg123 dependecies tapd can be started like e.g. `LD_LIBRARY_PATH=./dep/lib64/ ./tapd -s`

linking to mongoose does not work. maybe they don't wan't it to work due to a licensing issue with gpl?
however, as a resolution the public repo on github has been added to this repo as a submodule and mongoose.c will be complied when tapd is built.

## ui
### svg audio buttons
http://www.flaticon.com/authors/daniele-de-santis released under https://creativecommons.org/licenses/by/3.0/

#docs

## mxml
http://www.msweet.org/documentation/project3/Mini-XML.html

## shoutcast/icecast
### metadata
shoutcast's streaming protocol (and complying ones like icecast's) uses metadata tags embedded in the stream.
to receive those a http header `Icy-MetaData:1` needs to be added to the request. this can be achieved with e.g. `curl -H "Icy-MetaData:1" http://neo.m2stream.fr:8000/m280-128.mp3 -D header`. if everything went well the server will add `icy-metaint` to the respond headers.

this specifies the the byte location of the metadata length information in the stream and can either be non zero which means that there is metada or zero meaning that currently there is none.

to calculate the actual size of metadata bytes, the value at icy-metaint intervals needs to be multiplied by 16.
if there is metadata, at the end of the metadata also a null byte will be added. if there is no metadata the mp3 data will start right after the icy-metaint byte.

to illustrate this, lets say the metadata length identifier will be located in intervals of 16000 bytes (meaning icy-metaint was 16000) and the first occurrence contains metadata, then the stream will look something like this

```
 ---------------------------------------------------------------------------
| MP3-DATA | |        META-DATA        | |          MP3-DATA          | |
 ---------------------------------------------------------------------------
            ^                           ^                              ^
            |                           |                              |
         [16000] \                   nullbyte     [16000 + meta-data-lenght * 16 + nullbyte] \
          meta-data-lenght                         meta-data-lenght

```

further information on the protocol can be found on http://www.smackfu.com/stuff/programming/shoutcast.html.

#todos

- [ ] add logo consisting of a bar with multiple beer taps labled like "podcast", "webradio" and a audio jack cable plugged in
- [ ] check why mg_printf won't send a response ( currently mg_printf_http_chunk and mg_send_http_chunk are needed )
