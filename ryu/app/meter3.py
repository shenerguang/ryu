# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#TODO use mod_meter_entry() to limit the sending spead 

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import ofctl_v1_3
#from ryu.ofproto import ofproto_v1_3_parser#TODO if it ok???
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet

#TODO use OFPMeterMod() or use mod_meter_entry() directly
flow={}
band={}
band['type']='DROP'#OFPMeterBandDrop
band['rate']=100
band['burst_size']=10
flow['flags']='KBPS'
flow['meter_id']=1
flow['bands']=band#TODO if it is right??
flow['burst_size']=0#TODO?The burst_size field is used only if the flags field includes OFPMF_BURST. It defines the granularity
#of the meter, for all packet or byte burst which length is greater than burst value, the meter rate will
#always be strictly enforced. The burst value is in kilobits, unless the flags field includes OFPMF_PKTPS,
#in which case the burst value is in packets.
addmeter=0#TODO maybe it should be a list that can add meter to every switch
class Switch13(app_manager.RyuApp):
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

	def __init__(self, *args, **kwargs):
		super(Switch13, self).__init__(*args, **kwargs)
		self.mac_to_port = {}
                self.flow={}
                band={}
                band['type']='DROP'#OFPMeterBandDrop
                band['rate']=100
                band['burst_size']=10
                bands=[]
                bands.append(band)
                self.flow['flags']='KBPS'
                self.flow['meter_id']=1
                self.flow['bands']=bands#TODO if it is right??
                self.flow['burst_size']=0
                print self.flow
		self.addmeter=0
	@set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
	def switch_features_handler(self, ev):
		datapath = ev.msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.
		match = parser.OFPMatch()
		actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
		self.add_flow(datapath, 0, match, actions)



	def add_flow(self, datapath, priority, match, actions):
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser

		inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

		mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
		datapath.send_msg(mod)

	def add_meter(self, datapath, priority, match, actions):
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser

		inst = actions

		mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
		datapath.send_msg(mod)

	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	def _packet_in_handler(self, ev):
		msg = ev.msg
		datapath = msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		in_port = msg.match['in_port']

                pkt = packet.Packet(msg.data)
                eth = pkt.get_protocols(ethernet.ethernet)[0]

                dst = eth.dst
                src = eth.src

		dpid = datapath.id
#TODO add meter
		if self.addmeter==0:
			cmd=datapath.ofproto.OFPMC_ADD		
                        if datapath.ofproto.OFP_VERSION == ofproto_v1_3.OFP_VERSION:
                                print self.flow
                                ofctl_v1_3.mod_meter_entry(datapath,self.flow,cmd)#TODO complete the parameters def mod_meter_entry(dp, flow, cmd) #TODO check ofproto_v1_3_paser.py class OFPMeterMod(MsgBase):	
				self.addmeter=1
                                print 'add meter table'
                self.mac_to_port.setdefault(dpid, {})

                self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
		self.mac_to_port[dpid][src] = in_port

                if dst in self.mac_to_port[dpid]:
                        out_port = self.mac_to_port[dpid][dst]
                else:
                        out_port = ofproto.OFPP_FLOOD

                actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
                if out_port != ofproto.OFPP_FLOOD:
                        match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
                        self.add_flow(datapath, 1, match, actions)
                        print 'add flow'
			action = [parser.OFPInstructionMeter(self.flow.get('meter_id'))]
                        self.add_meter(datapath, 1, match, action)#TODO the action should be a meter TODO so we should add meter entry to meter table first
                        print 'add meter'
		
                data = None
                if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                        data = msg.data

                out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
                datapath.send_msg(out)
