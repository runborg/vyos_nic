#!/usr/bin/env python3
import fcntl
import re
import traceback
from subprocess import check_output, CalledProcessError
from vyos.configtree import ConfigTree
from  os import path 
from time import sleep
"""
Pre boot workflow
NB: All debuging needs to be returned to stderr or anoter logging location, this is because stdout is used to return data to UDEV

1:  create lockfile or wait for lock on file

2:  Look for config file /config/persistant-interface-names.conf?
2a: if found read it
2b: if not read config.boot for hw-id stamps

3:  if interface is found return name to stdout for processing by udevd and exit script

### If entering this section the interface is a new interface.

4: run interface trough biosdevname, 
   if a eth index is returned, use this as a "seed" to interface name mapper
   else return eth0 as "seed"

5: check if the interface is already, mapped in config from step 2
5a: if available proceed
5b: if not available start from "seed" interface and try all higher index values until a free spot is found

6: are we on a ro-root?
6a: yea, save "hint" to a file in /run/udev/ (ramdisk/tmpfs) to be read by post-boot script
6b: nope, save directly to #PERSISTANT_INTERFACE_FILE#

7: return new name to stdout for processing by udevd and exit script



# Helper functions
"""
def vyos_config_loaded():
    """ Returns True if the router configuration is loaded """
    # When this is False, the router is still booting and we could also be in ro-root
    # If this directory exists the router have loaded its configuration
   return path.isdir('/opt/vyatta/config/active/interfaces') 


class Locker:
    """ Simple file lock.. maybe also look at : https://github.com/derpston/python-simpleflock/blob/master/src/simpleflock.py """
    def __init__(self, filename):
        self._filename = filename
        self._f = None
    def wait_and_lock():
        """ Try to lock a file and wait until lock is aquired """
        # Waits forever to get a lock on the lockfile
        # If an unrelated error occures a exception is raised 
        self._f = open(self._filename, 'w')
        while true:
            try:
                fcntl.flock(filename, fcntl.LOCK_EX | dcnt.LOCK_NM)
                return
            except IOError as e:
                if e.errno == errno.EAGAIN:
                    # Do not raise error when waiting to aquire lock
                    time.sleep(0.1)
                else
                    # Raise on all unrelated errors
                    raise

     def unlock(self):
         if self._f:
             fcntl.flock(self._f, fcntl.LOCK_UN)
             close(self._f)
             self._f = None

    def __del__(self):
        self.unlock()


def read_hwids_from_configfile(filename):
    """ Read a vyos file and return all ethernet hw-id fields """

    interfaces = dict()
    with open(filename, 'r') as f:
        config = ConfigTree(f.read())

    for intf in config.list_nodes(['interfaces', 'ethernet']):
        if config.exists(['interfaces', 'ethernet', intf, 'hw-id']):
            interfaces[intf] = config.return_value(['interfaces', 'ethernet', intf, 'hw-id'])

    return interfaces

    
def log_to_dmesg(message):
    with open('/dev/kmsg','w') as f:
        f.write(message)


def read_persistant_names_file(filename):
    interfaces = dict()
    with open(filename, 'r', errors='replace') as f:
        for _l in enumerate(f.readlines()):
            index = _l[0]+1
            line = _l[1].strip()

            if not line:
                # Ignore empty lines
                continue

            if line.startswith("#") or line.startswith(";"):
                # Ignore comments
                continue

            entry = line.split("=", 2)
            if len(entry) != 2:
                # Ignore lines not following the syntax
                log_to_dmesg("vyos_nic_name: {}: Illegal entry found in config file, ignoring".format(index))
                continue

            intf = entry[0].strip()
            mac  = entry[1].strip()
            if not intf:
                # Empty interface name
                log_to_dmesg("vyos_nic_name: {}: Empty interfacename is found, ignoring".format(index))
                continue
            
            if len(intf) > 16:
                # Interface name to long
                log_to_dmesg("vyos_nic_name: {}: Interface name is to to long. Max length is 16 chars, ignoring".format(index))
                continue

            if not re.match(r'^[a-zA-Z0-9\-\.\_]+$', intf):
                # Interface with illegal character
                log_to_dmesg("vyos_nic_name: {}: Interface name contains illegal characters. Only a-z 0-9 - _ . is allowed, ignoring".format(index))
                continue

            if not mac:
                # Mac field is empty
                log_to_dmesg("vyos_nic_name: {}: MAC value can not be empty".format(index))

            if not re.match(r'^[a-zA-Z0-9\-\.\_\:]+$', mac):
                # Interface with illegal character
                log_to_dmesg("vyos_nic_name: {}: Interface name contains illegal characters in MAC field. Only a-z 0-9 - _ . : is allowed, ignoring".format(index))
                continue
            
            interfaces[intf] = mac
    return interfaces


def save_persistant_names_file(filename, interface, mac):
    try:
      with open(filename, 'r', errors='replace') as f:
        lines=f.readlines()
        print(lines)
        if len(lines) > 0:
            print(len(lines[-1].strip()))
            if len(lines[-1].strip()) == 0:
                print('popping')
                lines.pop()
            
        lines.append('{} = {}'.format(interface, mac))
        f.seek(0)
    except exception as e:
        log_to_dmesg('vyos_nic_name: save_persistant_names_file: Exception: {}'.format(traceback.format_exc()))

    with open(filename, 'w') as f:
        for l in lines:
            f.write(l.rstrip('\r\n'))
            f.write('\n')


def biosdevname(ifname):
    """ Biosdevname tries to find ethX names based on current PCI slot and DMI info """
    # Returns an empty string if it could not find a sutable name
    # Dont use biosdevname when running on Xen
    # This rule is copied from the old perl script, dont know if it is really needed anymore
    if path.isdir('/proc/xen'):
        log_to_dmesg("vyos_nic_name: {}: biosdevname is not running on Xen guests".format(ifname))
        return ''
    #biosdevname only runs on ethernet interfaces
    if not ifname.startswith('eth'):
        return ''
    # Let the interface name changes ordered by previous invocations of this
    # script complete before we call biosdevname.  If we don't, biosdevame
    # may generate incorrect name.
    sleep(1)
    try:
        new_name = check_output(['/sbin/biosdevname','--policy','all_ethN','-i',ifname]).strip()
        log_to_dmesg("vyos_nic_name: {}: biosdevname returned {} as interface name".format(ifname, new_name))
        return new_name
    except CalledProcessError:
        # biosdevname exited with an errorcode, will not use output
        log_to_dmesg("vyos_nic_name: {}: biosdevname returned an error when trying to resolve interface name".format(ifname))
    return ''

def find_interface_in_old_config(if_mac):
    # Finds an entry in the config.boot file, and returns the new name if found
    # Else return an empty string
    try:

        if path.isfile('/config/config.boot'):
            old_names = read_hwids_from_configfile('/config/config.boot')
            for name, mac in old_names.iteritems():
                if mac == if_mac:
                    return name
        else:
            log_to_dmesg("vyos_nic_name: Configuration read from persistant interface name file, skipping boot configuration")

    except Exception as E:
        log_to_dmesg("vyos_nic_name: Exception reading boot configuration file: \n{}".format(traceback.format_exc()))
    
    return ''



def main(if_name, if_mac):

    #2:  Look for config file /config/persistant-interface-names.conf?
    #    if found read it if not read config.boot for hw-id stamps
    hwids = {}
    #2a: Try to read persistant interface names from file
    if path.isfile('/config/interface-names.persist'):
        try: 
            hwids = read_persistant_names_file('/config/interface-names.persist')
        except Exception as E:
            log_to_dmesg("vyos_nic_name: Exception reading persistant interface name file: \n{}".format(traceback.format_exc()))

    
    #3:  if interface is found return without futher processing
    for new_name, mac in hwids.iteritems():
        if mac == if_mac:
            return new_name

    # No interface found with this mac address in persistent storage file
    
    ###########################################################################
    #  After this point consider the interfacec as a NEW interface detected   #
    ###########################################################################

    # Load new_assigned_interfaces temp-file to the hwids database
    # THIS NEEDS TO BE DONE! :) but is only relevant on bootup, because
    # after boot is finished we can save directly to the persistance-file
    if path.isfile('/run/udev/interface-names.tmp'):
        try:
            new_assigned = read_persistant_names_file('/run/udev/interface-names.tmp')
            hwids.update(new_assigned)
        except Exception as E:
            log_to_dmesg("vyos_nic_name: cant read temp-persistant-file Exception: {}".format(traceback.format_exc()))
    

    #2b:  MIGRATE FROM OLD CONFIG
    #     read persistant interface names from config.boot and se if we find this interface
    # HMM... need to check this,.. will it work? :S
    new_name = find_interface_in_old_config(if_mac)
    if new_name:
        if new_name in hwids:
            log_to_dmesg("vyos_nic_name: Error while saving old hw-id value to persistant storage, interface allready exists ")
            return None

        # Save interface to database
        if not vyos_config_loaded():
            # We are not on a fully booted system, saving as a interface hint
            save_persistant_names_file('/run/udev/interface-names.tmp', new_name, if_mac)
        else:
            # We are on a fully booted system
            save_persistant_names_file('/config/interface-names.persist', new_name, if_mac)
        
        return new_name

    # REGISTER NEW UNKNOWN INTERFACE
    #   if a eth index is returned, use this as a "seed" to interface name mapper 
    #   else return eth0 as "seed"
    new_name = biosdevname(if_name)
    if not new_name:
        # No name returned from biosdevname, setting eth0 as seed
        new_name = eth0

    if new_name in hwids:
        # Biosdevname index is in use, wee need to find a new one
    
        # Fetch index from new name as a seed, or use 0 as seed
        try:
            seed = int(re.search(r'\d+$', new_name)[0])
        except Exception as E:
            log_to_dmesg("vyos_nic_name: Exception fetching index from biosdevname, proceeding with seed = eth0, {}".format(traceback.format_exc()))
            seed = 0

        # Check name availabillity or increment the if_name until we get a match
        for x in xrange(seed, 10000):
            temp_name = 'eth{}'.format(x)
            if not temp_name in hwids:
                # The interface is not in persistant database
                # set as new name and break out of loop
                new_name = temp_name
                break
        else:
            log_to_dmesg("vyos_nic_name: WTF?? no available ifname's.. :S skipping ")
            return None

    # We now have a new index that is available to allocation

    log_to_dmesg("vyos_nic_name: New name for {} is {}".format(if_name, new_name))
    


    return new_name


    # Unlock for next instance to start


if __name__ == "__main__":
    # Step 1: Lock so only one instance at a time
    lock = Locker('/run/udev/ifname.lock')
    lock.lock_and_wait()

    name = main(sys.argv[0], sys.argv[1])
    lock.unlock() 
