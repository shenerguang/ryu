#!/bin/bash
bash cleanup_db.sh
ryu-manager --verbose --observe-links ryu.topology.switches ryu.app.ofctl_rest ryu.app.rest_topology ryu/app/diesi0.py &
sleep 15
python ryu/guiclient.py &
sleep 2
python ryu/MeterSender.py &
