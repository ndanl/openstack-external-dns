# coding=utf8
# vim: set fileencoding=utf8
# -*- coding: utf8 -*-
# ================================================================================================
import MySQLdb
import socket
import sys
from datetime import datetime
import ConfigParser
import os

# CONFIGs, SQL etc  [ start ] ================================================ [ start ] 
config = ConfigParser.SafeConfigParser()
# get the config at the db.config file in the same directory 
config.read(os.path.dirname(os.path.abspath(__file__))+'/db.config')
# assign the db configs
config_nova = dict(config.items("nova"))
config_pdns = dict(config.items("pdns"))

query = ("""select
i.id
, i.hostname
, lower(s.address) as floating_ip
from
instances i  left join instance_id_mappings m on i.id=m.id
left join fixed_ips f on m.uuid=f.instance_uuid
left join floating_ips s on f.id=s.fixed_ip_id
where true
-- and i.vm_state != 'deleted'
and i.host is not null""")

debug = False
#debug = True
epg_debug = False
#epg_debug = True
epg_add_hi_inet_resolve = False
#epg_add_hi_inet_resolve = True

# CONFIGs, SQL etc [ stop ] ================================================ [ stop ] 

if not epg_debug : print "["+str(datetime.now())+"] : Debug set to false at " + os.path.abspath(__file__)

try:
	# initialize db conection to nova
	cnx_nova = MySQLdb.connect(**config_nova)
	# open nova cursor
	cursor_nova = cnx_nova.cursor()
except MySQLdb.Error, e:
	print "["+str(datetime.now())+"] : " + "Error %d: %s" % (e.args[0], e.args[1])
	sys.exit (1)
	
# start the data processing
try:
	cursor_nova.execute(query)
	# initialize db conection to pdns
	try:
		cnx_pdns = MySQLdb.connect(**config_pdns)
		# open pdns cursor
		cursor_pdns = cnx_pdns.cursor()
	except MySQLdb.Error, e:
		print "["+str(datetime.now())+"] : " + "Error %d: %s" % (e.args[0], e.args[1])
		sys.exit (1)
except Exception, e:
	print "["+str(datetime.now())+"] : " + repr(e)
	sys.exit (1)
	
	
# clean the old records 
for (id,hostname,floating_ip) in cursor_nova:
	# clean openstack records 
	query_pdns_delete = (
		"delete from records where name= '%s.openstack.hi.inet';"
		)	
	try:
		cursor_pdns.execute(query_pdns_delete  % (hostname))
		if epg_debug : print ("["+str(datetime.now())+"] : " + "Executed : " + query_pdns_delete % (hostname)) 
	except MySQLdb.Error, e:
		print "["+str(datetime.now())+"] : " + "Error %d: %s" % (e.args[0], e.args[1])
		sys.exit (1)
	# clean hi.inet records 
	# if epg_add_hi_inet_resolve:
	query_pdns_delete_hi_inet = (
	"delete from records where name= '%s.hi.inet';"
	)	
	try:
		cursor_pdns.execute(query_pdns_delete_hi_inet  % (hostname))
		if epg_debug : print ("["+str(datetime.now())+"] : " + "Executed : " + query_pdns_delete_hi_inet % (hostname)) 
	except MySQLdb.Error, e:
		print "["+str(datetime.now())+"] : " + "Error %d: %s" % (e.args[0], e.args[1])
		sys.exit (1)	
	# clean TPRS
	query_pdns_delete_ptr = (
		"delete from records where content= '%s.openstack.hi.inet' and  name!='158.95.10.in-addr.arpa';"
		)	
	try:
		cursor_pdns.execute(query_pdns_delete_ptr  % (hostname))
		if epg_debug : print ("["+str(datetime.now())+"] : " + "Executed : " + query_pdns_delete_ptr % (hostname)) 
	except MySQLdb.Error, e:
		print "["+str(datetime.now())+"] : " + "Error %d: %s" % (e.args[0], e.args[1])
		sys.exit (1)

# inject the new ones 
for (id,hostname,floating_ip) in cursor_nova:
	# debug 
	try:
		socket.inet_aton(floating_ip)
		reverse_ip = '.'.join(floating_ip.split('.')[::-1])
		if debug : print ("["+str(datetime.now())+"] : " + "test : " + floating_ip)
		# execute the SQL DNS
		try:
			query_pdns_insert = (
			"insert into records (domain_id, name, content, type,ttl,prio,last_update) "
			"VALUES (2,'%s.openstack.hi.inet','%s','A',120,NULL,now());"
			)	
			cursor_pdns.execute(query_pdns_insert  % (hostname,floating_ip))
			if epg_debug : print ("["+str(datetime.now())+"] : " + "Executed : " + query_pdns_insert % (hostname,floating_ip))			
		except MySQLdb.Error, e:
			print "["+str(datetime.now())+"] : " + "Error %d: %s" % (e.args[0], e.args[1])
			sys.exit (1)
		# executre DNS reverse hi.inet PTR
		if epg_add_hi_inet_resolve:
			try:
				query_pdns_hi_insert = (
				"insert into records (domain_id, name, content, type,ttl,prio,last_update) "
				"VALUES (2,'%s.hi.inet','%s','A',120,NULL,now());"
				)	
				cursor_pdns.execute(query_pdns_hi_insert  % (hostname,floating_ip))
				if epg_debug : print ("["+str(datetime.now())+"] : " + "Executed : " + query_pdns_hi_insert % (hostname,floating_ip))			
			except MySQLdb.Error, e:
				print "["+str(datetime.now())+"] : " + "Error %d: %s" % (e.args[0], e.args[1])
				sys.exit (1)	
		# executre DNS reverse PTR
		try:
			query_pdns_insert_ptr = (
			"insert into records (domain_id, name, content, type,ttl,prio,last_update,change_date) "
			"VALUES (2,'%s.in-addr.arpa','%s.openstack.hi.inet','PTR',60,NULL,now(),unix_timestamp(now()));"
			)
			cursor_pdns.execute(query_pdns_insert_ptr  % (reverse_ip,hostname))
			if epg_debug : print ("["+str(datetime.now())+"] : " + "Executed : " + query_pdns_insert_ptr % (reverse_ip,hostname))			
		except MySQLdb.Error, e:
			print "["+str(datetime.now())+"] : " + "Error %d: %s" % (e.args[0], e.args[1])
			sys.exit (1)
		# executre DNS reverse hi.inet PTR	
	except socket.error : 
		if debug : print ("["+str(datetime.now())+"] : " + "Skipping this one : {1}".format(query_pdns_insert))
	except TypeError : 
		if debug : print ("["+str(datetime.now())+"] : " + "cursor_nova: Skipping this one due to Null values for hostname" + hostname)

# commint the change 
cnx_pdns.commit()
# closae the pdns 
cursor_pdns.close()
cnx_pdns.close()
# closae the nova 
cursor_nova.close()
cnx_nova.close()

#2013-07-26.14.22.47
