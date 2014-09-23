import json
from time import sleep
import urllib2
import MySQLdb

__author__ = 'samuel'

REST_SERVER_ADDR = 'http://localhost:8080'

DBADRESS = 'localhost'
DBUSER = 'root'
DBPASSWD = 'mysql'
DBNAME = 'meshsr'

TOPO_PUSH_PERIOD = 5# count as sec

conn = MySQLdb.connect(host=DBADRESS, user=DBUSER, passwd=DBPASSWD, db=DBNAME)
conn.autocommit(True)
cursor = conn.cursor()

dp_cord_x = dict()
dp_cord_y = dict()
j_base_x = 20
j_base_y = 350
j_step_x = 120
j_step_y = 145
j_group = 15
j_core = j_base_y + j_step_y*2.5

dp_cord_x['0000000000000010'] = j_base_x + j_step_x*0
dp_cord_y['0000000000000010'] = j_base_y

dp_cord_x['0000000000000011'] = j_base_x + j_step_x*1
dp_cord_y['0000000000000011'] = j_base_y

dp_cord_x['0000000000000012'] = j_base_x + j_step_x*1
dp_cord_y['0000000000000012'] = j_base_y + j_step_y

dp_cord_x['0000000000000013'] = j_base_x + j_step_x*0
dp_cord_y['0000000000000013'] = j_base_y + j_step_y

dp_cord_x['0000000000000014'] = j_base_x + j_step_x*0.5
dp_cord_y['0000000000000014'] = j_core

dp_cord_x['0000000000000015'] = j_base_x + j_group + j_step_x*2.5
dp_cord_y['0000000000000015'] = j_core

dp_cord_x['0000000000000016'] = j_base_x + j_group + j_step_x*2
dp_cord_y['0000000000000016'] = j_base_y + j_step_y

dp_cord_x['0000000000000017'] = j_base_x + j_group + j_step_x*3
dp_cord_y['0000000000000017'] = j_base_y + j_step_y

dp_cord_x['0000000000000018'] = j_base_x + j_group + j_step_x*3
dp_cord_y['0000000000000018'] = j_base_y

dp_cord_x['0000000000000019'] = j_base_x + j_group + j_step_x*2
dp_cord_y['0000000000000019'] = j_base_y

dp_cord_x['0000000000000020'] = j_base_x + j_group*2 + j_step_x*4
dp_cord_y['0000000000000020'] = j_base_y

dp_cord_x['0000000000000021'] = j_base_x + j_group*2 + j_step_x*5
dp_cord_y['0000000000000021'] = j_base_y

dp_cord_x['0000000000000022'] = j_base_x + j_group*2 + j_step_x*5
dp_cord_y['0000000000000022'] = j_base_y + j_step_y

dp_cord_x['0000000000000023'] = j_base_x + j_group*2 + j_step_x*4
dp_cord_y['0000000000000023'] = j_base_y + j_step_y

dp_cord_x['0000000000000024'] = j_base_x + j_group*2 + j_step_x*4.5
dp_cord_y['0000000000000024'] = j_core

dp_cord_x['0000000000000025'] = j_base_x + j_group*3 + j_step_x*6.5
dp_cord_y['0000000000000025'] = j_core

dp_cord_x['0000000000000026'] = j_base_x + j_group*2 + j_step_x*6
dp_cord_y['0000000000000026'] = j_base_y + j_step_y

dp_cord_x['0000000000000027'] = j_base_x + j_group*2 + j_step_x*7
dp_cord_y['0000000000000027'] = j_base_y + j_step_y

dp_cord_x['0000000000000028'] = j_base_x + j_group*2 + j_step_x*7
dp_cord_y['0000000000000028'] = j_base_y

dp_cord_x['0000000000000029'] = j_base_x + j_group*2 + j_step_x*6
dp_cord_y['0000000000000029'] = j_base_y 

def _debug(mess):
    print "*************************"
    print mess
    print "*************************"


def _find_port_id(dpid, port_no):
    sql = "SELECT portID FROM ports WHERE dpid='%s' AND number='%s';" \
          % (dpid, port_no)
    count = cursor.execute(sql)
    assert count == 1, "check your initial topology"
    result = cursor.fetchone()
    return str(result[0])


# update the switches table and ports table
def update_switches(switches_json):
    sql = "SELECT * FROM switches"
    num_dps = cursor.execute(sql)
    # TODO assumption: that there are no switches to leave or add into this demo.
    if num_dps != 0:
        return

    for switch in switches_json:
        switch_dpid = switch['dpid'].encode()
        sql = "INSERT INTO switches VALUE ('%s', '%s', '%s');" \
              % (switch_dpid, dp_cord_x[switch_dpid], dp_cord_y[switch_dpid])
        cursor.execute(sql)
        _debug(sql)

        for port in switch['ports']:
            port_dpid = port['dpid'].encode()
            port_name = port['name'].encode()
            port_hw_addr = port['hw_addr'].encode()
            port_port_no = port['port_no'].encode()
            sql = "INSERT INTO ports VALUE (NULL, '%s', '%s', '%s', '%s');" \
                  % (switch_dpid, port_name, port_hw_addr, port_port_no)
            _debug(sql)
            cursor.execute(sql)


def _conv_str(prev_links):
    # From ((L,L)...) to [(str,str)...]
    new_prev_links = []
    for p_link in prev_links:
        str_1 = str(p_link[0])
        str_2 = str(p_link[1])
        new_prev_links.append((str_1, str_2))
    return new_prev_links


def _to_du(prev_links):
    new_bi_links = []
    for p_link in prev_links:
        str_1 = str(p_link[0])
        str_2 = str(p_link[1])
        new_bi_links.append((str_1, str_2))
        new_bi_links.append((str_2, str_1))
    return new_bi_links

def update_phylink(now_links_json):
    sql = "SELECT srcPort,dstPort FROM phyLink"
    num_prev_links = cursor.execute(sql)
    prev_links = cursor.fetchall()

    if num_prev_links == 0:
        for link in now_links_json:
            src = link['src']
            src_dpid = src['dpid'].encode()
            src_port_no = src['port_no'].encode()
            # src_hw_addr = src['hw_addr'].encode()
            src_port_id = _find_port_id(src_dpid, src_port_no)

            dst = link['dst']
            dst_dpid = dst['dpid'].encode()
            dst_port_no = dst['port_no'].encode()
            # dst_hw_addr = dst['hw_addr'].encode()
            dst_port_id = _find_port_id(dst_dpid, dst_port_no)

            sql = "SELECT * FROM phyLink WHERE srcPort=%s AND dstPort=%s" % (dst_port_id, src_port_id)
            cnt = cursor.execute(sql)
            if cnt == 0:
                sql = "INSERT INTO phyLink VALUE (NULL, %s, %s);" \
                      % (src_port_id, dst_port_id)
                conn.commit()
                _debug(sql)
                cursor.execute(sql)
        return
    # No changes about link
    if num_prev_links == len(now_links_json)/2:
        return
    # some link add or delete.
    current_links = []
    for link in now_links_json:
        src = link['src']
        src_dpid = src['dpid'].encode()
        src_port_no = src['port_no'].encode()

        dst = link['dst']
        dst_dpid = dst['dpid'].encode()
        dst_port_no = dst['port_no'].encode()

        src_port_id = _find_port_id(src_dpid, src_port_no)
        dst_port_id = _find_port_id(dst_dpid, dst_port_no)
        current_links.append((src_port_id, dst_port_id))

    prev_links = _conv_str(prev_links)
    prev_links = _to_du(prev_links)
    if len(prev_links) < len(current_links):
        # link add
        diff_links = set(current_links).difference(set(prev_links))
        for d_link in diff_links:
            src_port_id = d_link[0]
            dst_port_id = d_link[1]

            sql = "SELECT * FROM phyLink WHERE srcPort=%s AND dstPort=%s" % (dst_port_id, src_port_id)
            cnt = cursor.execute(sql)
            if cnt == 0:
                sql = "INSERT INTO phyLink VALUE (NULL, %s, %s);" % (src_port_id, dst_port_id)
                _debug(sql)
                cursor.execute(sql)
    else:
        # link del
        diff_links = set(prev_links).difference(set(current_links))
        for d_link in diff_links:
            src_port_id = d_link[0]
            dst_port_id = d_link[1]
            sql = "DELETE FROM phyLink WHERE srcPort=%s AND dstPort=%s" % (src_port_id, dst_port_id)
            _debug(sql)
            cursor.execute(sql)

def topologypusher_init():
    cursor.execute("DELETE FROM phyLink")
    cursor.execute("DELETE FROM ports")
    cursor.execute("DELETE FROM switches")
    
def topoloaypusher_main():
    # Get JSONs from RYU controller.
    response_switches = urllib2.urlopen(REST_SERVER_ADDR + '/v1.0/topology/switches').read()
    switches_json = json.loads(response_switches)

    response_links = urllib2.urlopen(REST_SERVER_ADDR + '/v1.0/topology/links').read()
    links_json = json.loads(response_links)

    update_switches(switches_json)
    update_phylink(links_json)

    #Sleep for a while to avoid high load to SQLServer.

