#!/usr/bin/env python3

# Post-boot script to save new adresses to persistent interface names file post bootup.
# Data is collected from the temporary file
import fcntl


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




def main():
    # Read all entries in permanent persistant file

    # Read all entries in temp file

    # Check if interface it there already, log error if it is

    # Save entry to file



if __name__ == "__main__":
    lock = Locker('/run/udev/ifname.lock')
    lock.lock_and_wait()

    name = main(sys.argv[0], sys.argv[1])
    lock.unlock() 