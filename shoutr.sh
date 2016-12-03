#! /usr/bin/env bash

set -o nounset; set -o pipefail

stream_name="$1"
stream_url="$2"
address="$3"
port="$4"

stream_file="${stream_name}.out"

shoutr "$stream_url" >> "$stream_file" &
shoutr_pid=$!

trap "kill $shoutr_pid" EXIT

while true
do
  tail -n 1 "$stream_file" | {
    read stream_title
    printf "%s\n" \
      "<!DOCTYPE html>" \
      "<body>" \
      "<center><font size=\"7\">" \
        "$stream_title" \
      "</font></center>" \
      "</body>" |
    nc -l $address $port
  }
done
