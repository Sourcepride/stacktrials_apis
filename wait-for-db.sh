#!/usr/bin/env bash
# wait-for-db.sh <host>:<port> -- <command>
set -e
  
host="$1"
shift
cmd="$@"

until nc -z $(echo $host | cut -d: -f1) $(echo $host | cut -d: -f2); do
  >&2 echo "Waiting for $host to be available..."
  sleep 2
done

>&2 echo "$host is available - running command"
exec $cmd