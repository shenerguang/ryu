#!/bin/bash
mysql -h "localhost" -u "root" "-pmysql" "meshsr" -e "delete from flowEntry"
mysql -h "localhost" -u "root" "-pmysql" "meshsr" -e "delete from meshsr_connection"
mysql -h "localhost" -u "root" "-pmysql" "meshsr" -e "delete from meshsr_node"
mysql -h "localhost" -u "root" "-pmysql" "meshsr" -e "delete from phyLink"
mysql -h "localhost" -u "root" "-pmysql" "meshsr" -e "delete from serverNIC"
mysql -h "localhost" -u "root" "-pmysql" "meshsr" -e "delete from ports"
mysql -h "localhost" -u "root" "-pmysql" "meshsr" -e "delete from switches"
