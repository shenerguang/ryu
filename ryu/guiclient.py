import json
from time import sleep
import MySQLdb
import copy
import topologyserver

__author__ = 'samuel'

REST_SERVER_ADDR = 'http://localhost:8080'

DBADRESS = 'localhost'
DBUSER = 'root'
DBPASSWD = 'mysql'
DBNAME = 'meshsr'

conn = MySQLdb.connect(host=DBADRESS, user=DBUSER, passwd=DBPASSWD, db=DBNAME)
conn.autocommit(True)
cursor = conn.cursor()

GUI_ADAPTER_REFRESH_PERIOD = 3

link_nums = 0

def activate_link(cmplt_flow, ac_link):
    ac_bid = ac_link["node"]
    ac_eid = ac_link["peer"]

    for flow in cmplt_flow:
        _bid = flow["bid"]
        _eid = flow["eid"]
        if (_bid == ac_bid and _eid == ac_eid) or (_bid == ac_eid and _eid == ac_bid):
            flow["type"] = "con"
            return cmplt_flow


# make the type from dis to conn in complete_flow
def find_peerNICID_from_portID(portID):
    _sql = "SELECT serNICID FROM serverNIC WHERE peer = %s" % str(portID)
    _cnt = cursor.execute(_sql)
    assert _cnt == 1
    _peerNICID = cursor.fetchone()
    return _peerNICID[0]


# find the owner of the port
def find_dpid_from_port(portID):
    _sql = "SELECT dpid FROM ports WHERE portID=%s" % str(portID)
    _cnt = cursor.execute(_sql)
    assert _cnt == 1
    dpid = cursor.fetchone()
    return dpid[0]


def push_all_nodes():
    cursor.execute("DELETE FROM meshsr_node")
    cursor.execute("SELECT * FROM serverNIC")
    NICs = cursor.fetchall()

    cursor.execute("SELECT * FROM switches")
    dps = cursor.fetchall()

    for dp in dps:
        assert len(dp) == 3
        # dp[0]:dpid(char16)
        # dp[1]:x(int11)
        # dp[2]:y(int11)
        sql = "INSERT INTO meshsr_node VALUE(NULL, '%s', '%s', '%s', 0, 'dpid:%s')" \
              % (dp[0], dp[1], dp[2], dp[0])
        cursor.execute(sql)

    for nic in NICs:
        assert len(nic) == 3
        # nic[0]:serNICID(char16)
        # nic[1]:peer(int11)
        # nic[2]:MAC(varchar20)
        sql = "INSERT INTO meshsr_node VALUE(NULL, '%s', '%s', '%s', 1, 'server_nic_MAC:%s')" \
              % (nic[0], 0, 0, nic[2])
        cursor.execute(sql)


def push_phy_link():
    default_flow = list()
    cursor.execute("DELETE FROM meshsr_connection WHERE flow_info = 'default';")

    cursor.execute("SELECT * FROM phyLink")
    links_dps = cursor.fetchall()
    for link_dp in links_dps:
        #ensure every entry has 3 fields.
        assert len(link_dp) == 3
        # link_dp[0]:phyLinkID(int11)
        # link_dp[1]:srcPort(int11)
        # link_dp[1]:dstPort(int11)
        link_id = link_dp[0]
        src_port = link_dp[1]
        dst_port = link_dp[2]

        sql = "SELECT dpid FROM ports WHERE portID=%s" % src_port
        cnt = cursor.execute(sql)
        assert cnt == 1
        src_dpid = cursor.fetchone()[0]

        sql = "SELECT dpid FROM ports WHERE portID=%s" % dst_port
        cnt = cursor.execute(sql)
        assert cnt == 1
        dst_dpid = cursor.fetchone()[0]

        default_flow.append(
            dict(bid=src_dpid, eid=dst_dpid, type="dis")
        )

    cursor.execute("SELECT * FROM serverNIC")
    links_network_card_interface = cursor.fetchall()
    for link_NIC in links_network_card_interface:
        assert len(link_NIC) == 3
        # link_NIC[0]:serNICID(char16)
        # link_NIC[1]:peer(int11)
        # link_NIC[2]:MAC(varchar20)
        serNICID = link_NIC[0]
        peer_port = link_NIC[1]
        sql = "SELECT dpid FROM ports WHERE portID=%s" % peer_port
        cnt = cursor.execute(sql)
        assert cnt == 1
        peer_dpid = cursor.fetchone()[0]

        default_flow.append(
            dict(bid=serNICID, eid=peer_dpid, type="dis")
        )

    # FIXME the links between dps are bidirection but the dp2server.
    sql = "INSERT INTO meshsr_connection VALUE (NULL, 'default', '%s','physical links','')" \
          % (json.dumps(default_flow))
    cursor.execute(sql)
    return default_flow


def push_flows(default_flow):
    # adapter for every single flow in meshsr_connection
    cursor.execute("DELETE FROM meshsr_connection WHERE flow_info != 'default';")
    flow_ids = list()

    flow_ids_num = cursor.execute("SELECT DISTINCT flowID FROM flowEntry")
    assert flow_ids_num != 0
    # TODO assuming that there must be entries.
    resu_flowIDs = cursor.fetchall()
    for f in resu_flowIDs:
        flow_ids.append(f[0])

    for flow in flow_ids:
        sql = "SELECT flowSeqNum, dpid, inPort, outPort, meterValue FROM flowEntry " \
              "WHERE flowID=%s ORDER BY flowSeqNum" % flow
        cnt = cursor.execute(sql)
        assert cnt != 0
        entries = cursor.fetchall()
        # add single_flow into database
        complete_flow = copy.deepcopy(default_flow)
        # complete_flow = list({
        #     "bid": None
        #     "eid": None
        #     "type": None
        # })
        prev_dpid = None
        #print complete_flow
        for entry in entries:
            seq = entry[0]
            curr_dpid = entry[1]
            in_port = entry[2]
            out_port = entry[3]
            meter = entry[4]

            if seq == 0:
                serNICID = find_peerNICID_from_portID(in_port)
                active_link = dict(node=serNICID, peer=curr_dpid)
                print active_link
                complete_flow = activate_link(complete_flow, active_link)
                prev_dpid = curr_dpid

            elif seq != len(entries) - 1:
                active_link = dict(node=prev_dpid, peer=curr_dpid)
                complete_flow = activate_link(complete_flow, active_link)
                prev_dpid = curr_dpid

            else:
                active_link = dict(node=prev_dpid, peer=curr_dpid)
                complete_flow = activate_link(complete_flow, active_link)
                # add the final server linking it.
                #print out_port
                print active_link
                serNICID = find_peerNICID_from_portID(out_port)
                active_link = dict(node=curr_dpid, peer=serNICID)
                complete_flow = activate_link(complete_flow, active_link)
        print complete_flow

        # Add the Meter Value into Database.
        control_node = list()
        for entry in entries:
            curr_dpid = entry[1]
            meter_value = entry[4]

            control_node.append(dict(nid=curr_dpid, meter=meter_value))

        sql = "INSERT INTO meshsr_connection VALUE (NULL, 'flow%s', '%s','hello_simple_flow','%s')" % (
            flow, json.dumps(complete_flow), json.dumps(control_node))
        cursor.execute(sql)


def get_link_nums():
    return cursor.execute("SELECT * FROM phyLink")

def gui_init():
    cursor.execute("DELETE FROM meshsr_node")
    cursor.execute("DELETE FROM meshsr_connection")

    push_all_nodes()
    push_phy_link()

def gui_update():
    sql = "SELECT * FROM flowEntry"
    cnt = cursor.execute(sql)
    print cnt
    if cnt != 0:
        push_all_nodes()
        link_now = get_link_nums()
        if link_now != link_nums:
            print 'link change'
            link_nums = link_now
            default_flow = push_phy_link()
            #print default_flow
            push_flows(default_flow)

topologyserver.topologypusher_init()
gui_init()
while True:
    topologyserver.topoloaypusher_main()
    sql = "SELECT * FROM flowEntry"
    cnt = cursor.execute(sql)
    print cnt
    if cnt != 0:
        push_all_nodes()
        link_now = get_link_nums()
        if link_now != link_nums:
            print 'link change'
            link_nums = link_now
            default_flow = push_phy_link()
            #print default_flow
            push_flows(default_flow)
    sleep(GUI_ADAPTER_REFRESH_PERIOD)
