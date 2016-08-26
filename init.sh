#! /bin/bash

case "$1" in
  start)
    if [[ $(cat /etc/debian_version 2>/dev/null) =~ ^8 ]]
    then
      LD_LIBRARY_PATH=dep/lib nohup ./tapd -s &
    else
      nohup ./tapd -s &
    fi
    ;;
  stop)
    echo -n "stop... "
    kill $(pgrep tapd)
    if [ $? -eq 0 ]
    then
      echo "SUCCESS"
    else
      echo "FAIL"
    fi
    ;;
  status)
    pgrep -fl tapd > /dev/null
    if [ $? -eq 0 ]
    then
      echo "running"
    else
      echo "stopped"
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    ;;
esac
