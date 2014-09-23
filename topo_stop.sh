#!/bin/bash

sudo killall ryu-manager
sudo pkill -f "python ryu/TopologyPusher.py"
sudo pkill -f "python ryu/GUIAdapter.py"
sudo pkill -f "python ryu/MeterSender.py"
