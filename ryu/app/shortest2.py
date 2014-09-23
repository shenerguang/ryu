#TODO collecting the servers' MAC addresses and set a period
#TODO using etac (the topology information) to compute the route
#for each flow and add the flow entries to the switches, then add them to mysql db
import time
import random
import MySQLdb
from ryu.base import app_manager
from ryu.topology import event
from ryu.controller.controller import Datapath
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import ofctl_v1_3
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology.switches import Switch
#from ryu.topology.switches import get_link, get_switch, Switch
from priodict import priorityDictionary
from ryu.topology import event


DBADDRESS = 'localhost'
DBUSER = 'root'
DBPASSWD = 'mysql'
DBNAME = 'meshsr'
#TODO add the topology 4,12 (the computeflowok4_7_3.py is the ok edition with no topology collecting and ff:ff:ff:ff:ff:ff flow entries)
#TODO add the flow entry about FF:FF:FF:FF:FF:FF to let them learn each other's MAC without flood
conn = MySQLdb.connect(host=DBADDRESS, user=DBUSER, passwd=DBPASSWD, db=DBNAME)
cursor = conn.cursor()
start=time.time()

def get_switch(app, dpid=None):
    rep = app.send_request(event.EventSwitchRequest(dpid))
    return rep.switches


def get_all_switch(app):
    return get_switch(app)


def get_link(app, dpid=None):
    rep = app.send_request(event.EventLinkRequest(dpid))
    return rep.links


def get_all_link(app):
    return get_link(app)

def Dijkstra(G,start,end=None):#TODO test that if there is no way between start and end???
    
    D = {}	# dictionary of final distances
    P = {}	# dictionary of predecessors
    Q = priorityDictionary()   # est.dist. of non-final vert.
    Q[start] = 0
	
    for v in Q:
        D[v] = Q[v]
        if v == end: break
		
        for w in G[v]:
            vwLength = D[v] + G[v][w]
            if w in D:
                if vwLength < D[w]:
                    raise ValueError, \
  "Dijkstra: found better path to already-final vertex"
            elif w not in Q or vwLength < Q[w]:
                Q[w] = vwLength
                P[w] = v
	
    return (D,P)
			
def shortestPath(G,start,end):
    D,P = Dijkstra(G,start,end)
    Path = []
    while 1:
        Path.append(end)
        if end == start: break
        end = P[end]
    Path.reverse()
    return Path



class SDNswitch(app_manager.RyuApp):
    OFP_VERSIONS = {ofproto_v1_3.OFP_VERSION}
    def __init__(self, *args, **kwargs):
        super(SDNswitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}#{dpid:{src:port},}
        self.flowEntryID = 0
        self.flowID = 0
        self.servernum = 0
        self.serNICID = 'F000'
        self.k=4
        self.half=10# the topology is half fattree(4)
        self.T=5000#TODO 1 ms,(10s)?
        #TODO add the parameters
        self.swlabel_IP = {0:'10.0.0.1',
                           1:'10.0.1.1',
                           2:'10.1.0.1',
                           3:'10.1.1.1',
                           4:'10.0.2.1',
                           5:'10.0.3.1',
                           6:'10.1.2.1',
                           7:'10.1.3.1',
                           8:'10.2.1.1',
                           9:'10.2.1.2'}
        self.dpid_to_label = {16:0,17:1,18:4,19:5,20:9,21:8,22:6,23:7,24:2,25:3}#read from the etac result, or the dpid,port->label,port? ?
        #TODO TODO 2014,4,14 the server's (label,bport):(dpid,port) should be dynamic
        self.bports_to_dports = {(0,2):(10,4),(0,3):(10,2),(1,2):(11,3),(1,3):(11,1),(2,2):(18,1),(2,3):(18,3),(3,2):(19,2),(3,3):(19,4),
                                 (4,0):(12,2),(4,1):(12,1),(4,2):(12,4),(5,0):(13,4),(5,1):(13,3),(5,2):(13,1),(6,0):(16,3),(6,1):(16,4),
                                 (6,2):(16,1),(7,0):(17,1),(7,1):(17,2),(7,2):(17,4),(8,0):(15,4),(8,1):(15,1),(9,0):(14,1),(9,1):(14,4)}
        #TODO#TODO test if it is ok? {(blueprint_switch_label,port):(dpid,port)}#TODO TODO prepare to be done, add etac to this file to get the parameters
        self.mac_to_dpid = {}#TODO server mac address -> the (dpid,port) of its connecting switch {mac:(dpid,port)}
        self.label_to_port = {(0,4):(3,0),(0,5):(2,0),(1,4):(3,1),(1,5):(2,1),(2,6):(3,0),(2,7):(2,0),(3,6):(3,1),(3,7):(2,1),(4,8):(2,0),(5,9):(2,0),(6,8):(2,1),(7,9):(2,1),
                              (4,0):(0,3),(5,0):(0,2),(4,1):(1,3),(5,1):(1,2),(6,2):(0,3),(7,2):(0,2),(6,3):(1,3),(7,3):(1,2),(8,4):(0,2),(9,5):(0,2),(8,6):(1,2),(9,7):(1,2)}
        self.label_to_dpid = {0:16,1:17,4:18,5:19,9:20,8:21,6:22,7:23,2:24,3:25}
        self.graph={(0,4):1,(0,5):1,(1,4):1,(1,5):1,(2,6):1,(2,7):1,(3,6):1,(3,7):1,(4,8):1,(5,9):1,(6,8):1,(7,9):1,
                    (4,0):1,(5,0):1,(4,1):1,(5,1):1,(6,2):1,(7,2):1,(6,3):1,(7,3):1,(8,4):1,(9,5):1,(8,6):1,(9,7):1}
        self.server1=''
        self.server2=''
        self.n=0
        self.m=0
        self.startnum=0
        self.G={}
        self.dpids_to_nums={}
        self.nums_to_dpids={}
        self.dpid_to_port={}
        self.graph=[]
        self.undirected=[]
        self.linkgraph=[]
        self.switch_num=4
        self.link_num=4
        self.switches = []
        self.links = {}
        self.topo_col_period_max = 120 #TODO will 2min be enough for the topology collecting ?
        self.topo_col_period = 0
        self.topo_col_num_max = 10 #after topo_col_num times get_links(), no matter whether the topology is complete or not, we will auto-configure adresses
        self.topo_col_num = 0
        self.edgenum=0
        for i in xrange(self.switch_num):
            self.graph.append([])
            self.undirected.append([])
            self.linkgraph.append([])
            for j in xrange(self.switch_num):
                self.graph[i].append(0)
                self.undirected[i].append(0)
                self.linkgraph[i].append(0)
        print 'init over'
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        print 'switch'
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        
    def add_flow(self, datapath, priority, match, actions):
        print 'add flow!!!!!!!!!!!!!!!'
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        idle_timeout=600
        hard_timeout=10
        mod = parser.OFPFlowMod(datapath=datapath,#idle_timeout=idle_timeout,hard_timeout=hard_timeout,
                                priority=priority,match=match, instructions=inst)
        datapath.send_msg(mod)
        print str(datapath)+' '+str(priority)+' '+str(match)+' '+str(inst)
    def delete_flow(self, datapath, match):
        print 'delete flow!!!!!!!!!!!!!!!'
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        #inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
        #                                     actions)]
        table_id=1
        #idle_timeout=6
        #hard_timeout=10
        #mod = parser.OFPFlowMod(datapath=datapath, table_id=table_id, command=OFPFC_DELETE, match=match, instructions=inst)
        mod = parser.OFPFlowMod(datapath=datapath, #table_id=table_id,#TODO
                                command=ofproto.OFPFC_DELETE, match=match)
        datapath.send_msg(mod)
        print str(datapath)+' '+str(match)#+' '+str(inst)
        
    def MACLearning(self, ev):
        print 'MACLearning'
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src
        strsrc=src.split(':')
        print src
        print dst
        dpid = datapath.id
        if None == self.mac_to_port.get(dpid):
            self.mac_to_port.setdefault(dpid, {})
                        
            self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

            #learn a mac address to avoid FLOOD next time
            self.mac_to_port[dpid][src]=in_port
            #self.mac_to_dpid[src]=(dpid,in_port)
            print 'mac_to_port['+str(dpid)+']'+'['+str(src)+']='+str(in_port)
            #only add server mac to the database
            #if '00'!=strsrc[0]:#TODO test, because only servermac address should be added to the data base
            
            sql="SELECT portID FROM ports WHERE MAC='%s';" \
             % (src)
            print sql
            count=cursor.execute(sql)
            result = cursor.fetchone()
            #conn.commit()
            nosrc='00:00:00:00:00:00'
            sql="SELECT portID FROM ports WHERE MAC='%s';" \
             % (nosrc)
            print sql
            count=cursor.execute(sql)
            noresult = cursor.fetchone()

            sql="SELECT serNICID FROM serverNIC WHERE MAC='%s';" \
             % (src)
            print sql
            count=cursor.execute(sql)
            resultser = cursor.fetchone()
            #conn.commit()
            nosrc='00:00:00:00:00:00'
            sql="SELECT serNICID FROM serverNIC WHERE MAC='%s';" \
             % (nosrc)
            print sql
            count=cursor.execute(sql)
            noresultser = cursor.fetchone()
            conn.commit()
            if noresult==result and noresultser==resultser:
                print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!add server!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
                self.servernum = self.servernum+1
                self.serNICID = 'F00000000000000'+str(self.servernum)#TODO when the server number > 10, this should be change
                self.mac_to_dpid[src]=(dpid,in_port)
                MAC=src
                port=in_port
                self.add_server_to_sql(self.serNICID, dpid, port, MAC)
                
                if 1==self.servernum:
                    self.server1=MAC
                elif 2==self.servernum:
                    self.server2=MAC
            else:
                print result
                
        elif None == self.mac_to_port.get(dpid).get(src):
            
            self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

            #learn a mac address to avoid FLOOD next time
            self.mac_to_port[dpid][src]=in_port
            #self.mac_to_dpid[src]=(dpid,in_port)
            print 'mac_to_port['+str(dpid)+']'+'['+str(src)+']='+str(in_port)
            #only add server mac to the database
            sql="SELECT portID FROM ports WHERE MAC='%s';" \
             % (src)
            print sql
            count=cursor.execute(sql)
            result = cursor.fetchone()
            #conn.commit()
            nosrc='00:00:00:00:00:00'
            sql="SELECT portID FROM ports WHERE MAC='%s';" \
             % (nosrc)
            print sql
            count=cursor.execute(sql)
            noresult = cursor.fetchone()

            sql="SELECT serNICID FROM serverNIC WHERE MAC='%s';" \
             % (src)
            print sql
            count=cursor.execute(sql)
            resultser = cursor.fetchone()
            #conn.commit()
            nosrc='00:00:00:00:00:00'
            sql="SELECT serNICID FROM serverNIC WHERE MAC='%s';" \
             % (nosrc)
            print sql
            count=cursor.execute(sql)
            noresultser = cursor.fetchone()
            conn.commit()
            if noresult==result and noresultser==resultser:
                print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!add server!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
                self.servernum = self.servernum+1
                self.serNICID = 'F00000000000000'+str(self.servernum)#TODO when the server number > 10, this should be change
                self.mac_to_dpid[src]=(dpid,in_port)
                MAC=src
                port=in_port
                self.add_server_to_sql(self.serNICID, dpid, port, MAC)
                
                if 1==self.servernum:
                    self.server1=MAC
                elif 2==self.servernum:
                    self.server2=MAC
            else:
                print result
        else:
            print 'server has been added!!!!!!!!!!!'
        
            
            #TODO the following flood of arp will make loop in fattree ....(data center topologies which has loop)
##        out_port=ofproto.OFPP_FLOOD
##        actions=[parser.OFPActionOutput(out_port)]
##        data=None
##        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
##            data=msg.data
##        out=parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,#TODO consider that this packet maybe lose (if it will has some problems?)
##                                in_port=in_port, actions=actions, data=data)#TODO actions should be the action for the datapath
##        datapath.send_msg(out)
        
    def add_flow_to_sql(self, flowEntryID, flowID, flowSeqNum, dpid, tableID, entryID, in_port, out_port, meterID, meterValue):
        #TODO check the port table to get inPort and outPort
        print 'add flow to sql'
        dbdpid='00000000000000'+str(int(dpid)/16)+str(int(dpid)%16)
        sql="SELECT portID FROM ports WHERE dpid='%s' AND number='%d';" \
             % (dbdpid, in_port)
        print sql
        count=cursor.execute(sql)
        result = cursor.fetchone()
        inPort=result[0]
        sql="SELECT portID FROM ports WHERE dpid='%s' AND number='%d';" \
             % (dbdpid, out_port)
        print sql
        count=cursor.execute(sql)
        result = cursor.fetchone()
        outPort=result[0]
                #TODO check if this flow entry exists
        sql="SELECT flowEntryID FROM flowEntry WHERE dpid='%s' AND inPort='%d';" \
             % (dbdpid, inPort)
        print sql
        count=cursor.execute(sql)
        result = cursor.fetchone()
        nodpid='0000000000000020'
        sql="SELECT flowEntryID FROM flowEntry WHERE dpid='%s';" \
             % (nodpid)
        print sql
        count=cursor.execute(sql)
        noresultflow = cursor.fetchone()
        conn.commit()
        if result != noresultflow:
            print 'the flow has existed'
            sql = "DELETE FROM flowEntry where flowEntryID='%d';" \
                  % (result[0])
            print sql
            cursor.execute(sql)
            conn.commit()
            flag=1
        else:
            flag=0
        sql = "INSERT INTO flowEntry VALUE (%s, %s, %s, '%s', %s, %s, %s, %s, %s, %s);" \
                % (flowEntryID, flowID, flowSeqNum, dbdpid, tableID, entryID, inPort, outPort, meterID, meterValue)#TODO
        #sql = "INSERT INTO flowEntry VALUE (NULL, '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s');" \
        #        % (flowID, flowSeqNum, dbdpid, tableID, entryID, inPort, outPort, meterID, meterValue)#TODO
        print sql
        cursor.execute(sql)
        conn.commit()
        return flag
    def add_server_to_sql(self, serNICID, dpid, port, MAC):
        #TODO check the port table to get peer (the switch port which is connected by the server)
        print dpid
        print port
        print MAC
        dbdpid='00000000000000'+str(int(dpid)/16)+str(int(dpid)%16)
        sql="SELECT portID FROM ports WHERE dpid='%s' AND number='%d';" \
             % (dbdpid, port)
        print sql
        count=cursor.execute(sql)
        result = cursor.fetchone()
        peer=result[0]
        sql = "INSERT INTO serverNIC VALUE ('%s', '%s', '%s');" \
              % (serNICID, peer, MAC)
        #sql = "INSERT INTO serverNIC VALUE (NULL, '%d', '%s');" \
        #      % (peer, MAC)
        print sql
        count=cursor.execute(sql)
        #test
        conn.commit()
        sql = "SELECT peer FROM serverNIC WHERE MAC='%s';"\
              % (MAC)
        count=cursor.execute(sql)
        result = cursor.fetchone()
        print 'result'
        print result
    def addflowsql(self, dst, dpid, in_port, out_port, flag):
        print 'add flow sql !!!!!!!!!!!!!!!!!!!!!!!!!!!'
        print dpid,in_port,out_port
        data_path=get_switch(self,dpid)#TODO test
        print type(data_path)
        print '!!!!!!!!!!!!!!!!!!!'
        print data_path
        datapath=data_path[0].dp#TODO test
        print 'datapath = '
        print datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        print 'dst = '+str(dst)
        print 'dpid = '+str(dpid)
        print 'in_port = '+str(in_port)
        print 'out port = '+str(out_port)
        actions=[parser.OFPActionOutput(out_port)]
        match=parser.OFPMatch(in_port=in_port,eth_dst=dst)
        if 1==flag:
            self.delete_flow(datapath, match)#TODO test delete flow!!

        print '!!!!!!!!!!!!!!!!!!add flow!!!!!!!!!!!!!!!!!!!!in_port='+str(in_port)+' dst='+str(dst)+' out_port='+str(out_port)+' dpid='+str(dpid)
        self.add_flow(datapath, 1, match, actions)

    def short(self,ev,src,dst,G):

        #TODO add the flow entries of ff:ff:ff:ff:ff:ff
        #TODO TODO just make ff:ff:ff:ff:ff:ff as the other server's mac (because there is only two server)
        #TODO after controller learning two servers' MAC, then add all the needing flow entries (4,bothway of MAC and ff:ff:ff:ff:ff:ff)
        #using self.mac_to_dpid to get the two servers' MAC and (dpid,port), then add the 4 flow entries
        
        print 'FFRouting'
        
        msg = ev.msg
        datapath = msg.datapath
        print type(datapath)
        print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        print datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

##        dst = eth.dst
##        src = eth.src
##        macsrc=src.split(':')
##        macdst=dst.split(':')
##        print src
##        print dst
##        if None==self.mac_to_dpid.get(src) or None==self.mac_to_dpid.get(dst):#TODO
##            print 'src or dst mac is not ok'
##            self.MACLearning(ev)
##            return
        dpid = datapath.id
        print '!!!!!!!!!!!!!dpid=!!!!!!!!!!!!1'
        print str(dpid)
        #TODO because if the switch has the flow entry it will not packet_in, when it packet_in we only
        #need to compute the route and set a living period for every flow entry 

        #TODO how to get the topology just add etac (error tolerance address configuration) to this file?
        #or write the blueprint id, port <-> dpid, port to the file ? then read that file ?????
        #TODO compute the route in the blueprint
        #and then get corresponding route in the physical graph (switch dpid as a node)


        f='ff:ff:ff:ff:ff:ff'
        #if None==self.mac_to
        srcsw=self.mac_to_dpid[src]
        dstsw=self.mac_to_dpid[dst]
        srcswip=self.swlabel_IP[self.dpid_to_label[srcsw[0]]].split('.')
        dstswip=self.swlabel_IP[self.dpid_to_label[dstsw[0]]].split('.')
        self.flowID=self.flowID+1
        flowSeqNum=0
        tableID=0#TODO TODO prepare to be done how to get the value of tabelID, entryID ?
        entryID=0
        inPort=in_port
        outPort=0
        meterID=0#TODO TODO prepare to be done write meter
        meterValue=100#kb/s
        # install a flow to avoid packet_in next time
        #TODO how to use dpid to get datapath get_switch(dpid)?

        #TODO use the shortest path to compute the flow
        start=self.dpids_to_nums[srcsw[0]]
        end=self.dpids_to_nums[dstsw[0]]
        path=shortestPath(G,start,end)#TODO test if there is no path between them
        print path
        #TODO add flow entry to the self.nums_to_dpids[path[i]], with the first in port (srcsw[1]), out_port (self.dpid_to_port[()])
        if len(path)==0:
            print 'no path'
            return
        x=1
        dpflag=0
        for i in xrange(len(path)):
            dpid=self.nums_to_dpids[path[i]]
            if x==1:
                s=dpid
                t=self.nums_to_dpids[path[i+1]]
                in_port=srcsw[1]
                out_port=self.dpid_to_port[(s,t)][0]
                flag=self.add_flow_to_sql(self.flowEntryID, self.flowID, flowSeqNum, dpid, tableID, entryID, in_port, out_port, meterID, meterValue)
                self.addflowsql(dst, dpid, in_port, out_port, flag)
                print 'add_flow'
                self.flowEntryID=self.flowEntryID+1
                actions=[parser.OFPActionOutput(out_port)]
                
                self.addflowsql(f, dpid, in_port, out_port, 0)#TODO if it need to packet out the packet ?? test

            elif x<len(path):
                s=dpid
                t=self.nums_to_dpids[path[i+1]]
                in_port=self.dpid_to_port[(self.nums_to_dpids[path[i-1]],s)][1]
                out_port=self.dpid_to_port[(s,t)][0]
                flag=self.add_flow_to_sql(self.flowEntryID, self.flowID, flowSeqNum, dpid, tableID, entryID, in_port, out_port, meterID, meterValue)
                self.addflowsql(dst, dpid, in_port, out_port, flag)
                print 'add_flow'
                self.flowEntryID=self.flowEntryID+1
                actions=[parser.OFPActionOutput(out_port)]
                
                self.addflowsql(f, dpid, in_port, out_port, 0)

                
            else:
                s=self.nums_to_dpids[path[i-1]]
                t=dpid
                in_port=self.dpid_to_port[(s,t)][1]
                out_port=dstsw[1]
                flag=self.add_flow_to_sql(self.flowEntryID, self.flowID, flowSeqNum, dpid, tableID, entryID, in_port, out_port, meterID, meterValue)
                self.addflowsql(dst, dpid, in_port, out_port, flag)
                print 'add_flow'
                self.flowEntryID=self.flowEntryID+1
                actions=[parser.OFPActionOutput(out_port)]
                
                self.addflowsql(f, dpid, in_port, out_port, 0)
                

            if datapath.id==s:
                dpaction=actions
                dpflag=1
            x=x+1
        if 1==dpflag:    
            in_port = msg.match['in_port']
            data=None
            out=parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,#TODO consider that this packet maybe lose (if it will has some problems?)
                                in_port=in_port, actions=dpaction, data=data)#TODO actions should be the action for the datapath
            datapath.send_msg(out) 

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

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        #TODO using two methods to do two things respectively ?
        #TODO using server MAC learning period T to separate the two methods ?
##        end=time.time()
##        if (end-start)*1000 < self.T:
##            #TODO compute the route
##            print (end-start)*1000
##            self.MACLearning(ev)
##        else:
##            print (end-start)*1000
##            #TODO learning server MAC
##            self.Routing(ev)
        
        #TODO add the topology collecting periodically
        self.edgenum=0
        start = time.time()
        print start
        self.switches = get_switch(self)
        self.links = get_link(self)
        self.topo_col_num = self.topo_col_num + 1
        end = time.time()
        print end
        print 'topology collecting time:'
        print end-start
        self.topo_col_period = self.topo_col_period + end-start

        #n=len(self.switches)
        #m=len(self.links)
##        self.startnum=0
##        self.dpids_to_nums={}
##        self.nums_to_dpids={}
        print 'dpids nums:'
        for switch in self.switches:#TODO this may has error
            if self.dpids_to_nums.get(switch.dp.id)==None:
                self.nums_to_dpids[self.startnum] = switch.dp.id
                self.dpids_to_nums[switch.dp.id] = self.startnum
                print str(switch.dp.id)+' '+str(self.startnum)
                self.startnum = self.startnum + 1
        print self.dpids_to_nums
        self.n=self.startnum
        print 'edges:'
        self.linkgraph=[]
        for i in xrange(self.switch_num):
            self.linkgraph.append([])
            for j in xrange(self.switch_num):
                self.linkgraph[i].append(0)
        for link in self.links:
            self.edgenum=self.edgenum+1
            srcnum = self.dpids_to_nums[link.src.dpid]
            dstnum = self.dpids_to_nums[link.dst.dpid]
            self.linkgraph[srcnum][dstnum]=1
            if self.graph[srcnum][dstnum]==0 and self.graph[dstnum][srcnum]==0:
                print str(srcnum)+' '+str(dstnum)
                self.dpid_to_port[(link.src.dpid, link.dst.dpid)] = (link.src.port_no, link.dst.port_no)
                self.dpid_to_port[(link.dst.dpid, link.src.dpid)]=(link.dst.port_no, link.src.port_no)
                #print>>devicegraph, str(srcnum)+' '+str(dstnum)
                self.graph[srcnum][dstnum] = 1
                self.graph[dstnum][srcnum] = 1
                self.undirected[srcnum][dstnum] = 1
                self.m=self.m+1
        self.G={}
        for i in xrange(self.switch_num):
            self.G[i]={}
            for j in xrange(self.switch_num):
                if self.linkgraph[i][j]==1 and self.linkgraph[j][i]==1:#TODO if only one way is ok then regard it as not ok
                    self.G[i][j]=1
        print self.G
        flag=0
        if self.n<4 or self.m<4 or self.topo_col_num<self.topo_col_num_max or self.topo_col_period<self.topo_col_period_max:#TODO test,but when the edge is error, then it will not be ok
            flag=1#TODO
        print 'topology ok'
        if self.servernum<2:
            self.MACLearning(ev)
            if 2==self.servernum: #and 0==flag:
                src=self.server1
                dst=self.server2
                self.short(ev, src, dst, self.G)#add the flow entries of FF:FF:FF:FF:FF:FF
                src=self.server2
                dst=self.server1
                self.short(ev, src, dst, self.G)                
        elif 2==self.servernum or self.edgenum!=8: #and 0==flag:
            #it means that two servers' MAC have been added, then add the
            src=self.server1
            dst=self.server2
            self.short(ev, src, dst, self.G)#add the flow entries of FF:FF:FF:FF:FF:FF
            src=self.server2
            dst=self.server1
            self.short(ev, src, dst, self.G)
            
##        if self.m!=4:#TODO when the edge has error ,recompute the routing between two servers
##            
##            src=self.server1
##            dst=self.server2
##            self.short(ev, src, dst, self.G)#add the flow entries of FF:FF:FF:FF:FF:FF
##            src=self.server2
##            dst=self.server1
##            self.short(ev, src, dst, self.G)    


