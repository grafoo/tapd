#! /usr/bin/env bash

set -o nounset; set -o pipefail

stream_name="$1"
stream_url="$2"
address="$3"
port="$4"

stream_file="${stream_name}.out"

if $(nc -h 2>&1 | head -n 1 | grep -q "^OpenBSD.*$")
then
  srv="nc -l $address $port"
else
  srv="nc -l -s $address -p $port"
fi

shoutr "$stream_url" >> "$stream_file" &
shoutr_pid=$!

trap "kill $shoutr_pid" EXIT

while true
do
  tail -n 1 "$stream_file" | {
    read stream_title
    printf "%s\n" \
      "<!DOCTYPE html>" \
      "<html>" \
      "<body>" \
      "<center><font size=\"7\">" \
        "$stream_title" \
      "</font></center>" \
      "</body>" \
      "</html>" |
    $srv
  }
done
