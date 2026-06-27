#!/bin/bash
exec /home/dietpi/.local/bin/copyparty \
  -a admin:admin \
  -v '/home/dietpi/downloads::r:A,admin' \
  -i 0.0.0.0 -p 8080 \
  --grid
