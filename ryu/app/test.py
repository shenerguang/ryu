import time
import random
import MySQLdb
from ryu.base import app_manager
from ryu.controller.controller import Datapath
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import ofctl_v1_3
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology.switches import get_switch, get_link, Switch
class SDNswitch(app_manager.RyuApp):
    OFP_VERSIONS = {ofproto_v1_3.OFP_VERSION}
    def __init__(self, *args, **kwargs):
        super(SDNswitch, self).__init__(*args, **kwargs)
    @set_ev_cls(ofp_event.EventOFPPortStatus)
    def _port_status_handler(self, ev):
        print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!port change!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        #print ev.port
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        dpid = dp.id
        print 'dp=' + str(dp)
        print 'port=' + str(msg.desc)
        print dpid
        if msg.reason == ofp.OFPPR_ADD:
            reason = 'ADD'
        elif msg.reason == ofp.OFPPR_DELETE:
            reason = 'DELETE'
        elif msg.reason == ofp.OFPPR_MODIFY:
            reason = 'MODIFY'#TODO the reason only has EventOFPPortStatus
        else:
            reason = 'UNKNOWN'

        print 'reason=' + reason
