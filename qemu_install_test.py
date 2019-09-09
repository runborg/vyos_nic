#!/usr/bin/env python3
import pexpect
import sys
import os
import time
import argparse
import subprocess
import random
import traceback
import logging
import re
from io import BytesIO, StringIO
from datetime import datetime

EXCEPTION = 0
now = datetime.now()


parser = argparse.ArgumentParser(description='Install and start a test VyOS vm.')
parser.add_argument('iso', help='ISO file to install')
parser.add_argument('disk', help='name of disk image file', 
                            nargs='?',
                            default='testinstall-{}-{}.img'.format(now.strftime('%Y%m%d-%H%M%S'),
                                                                   "%04x" % random.randint(0,65535)))
parser.add_argument('--keep', help='Do not remove disk-image after installation', 
                              action='store_true',
                              default=False)
parser.add_argument('--silent', help='Do not show output from system unless an error has occured', 
                              action='store_true',
                              default=False)                           
args = parser.parse_args()

# Logging taken from here: https://mail.python.org/pipermail/python-list/2010-March/570847.html
# this will be the method called by the pexpect object to log



class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = b''

    def write(self, buf):
        if b'\n' in buf:
            for line in buf.rstrip().splitlines():
                self.logger.log(self.log_level, line.rstrip())
        else:
            self.linebuf += buf

    def flush(self):
        pass

# Setting up logger
log = logging.getLogger()
log.setLevel(logging.DEBUG)
# give the logger the methods required by pexpect

stl = StreamToLogger(log)
#log.write = stl.write
#log.flush = _doNothing

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)



if args.silent:
    output = BytesIO()
else:
    output = sys.stdout.buffer

if not os.path.isfile(args.iso):
    sys.exit("# ERROR: Unable to find iso image to install")


# Creating diskimage!!

if not os.path.isfile(args.disk):
    print("#"*80)
    print("#  Creating Disk")
    print("#"*80)
    c = subprocess.check_output(["qemu-img", "create", args.disk, "2G"])
    print(c.decode())
else:
    print("# Diskimage already exists, using the existing one")



try:
    #################################################
    # Installing image to disk
    #################################################
    print("\n\n\n")
    print("#"*80)
    print("#  Installing system")
    print("#"*80)

    cmd = """qemu-system-x86_64 \
    -name "TESTVM" \
    -m 1G \
    -nic user,model=virtio,mac=52:54:99:12:34:56,hostfwd=tcp::2299-:22 \
    -machine accel=kvm \
    -cpu host -smp 2 \
    -vnc 0.0.0.0:99 \
    -nographic \
    -boot d -cdrom {CD} \
    -drive format=raw,file={DISK}
    """.format(CD=args.iso, DISK=args.disk)
    print("Executing command: {}".format(cmd))
    c = pexpect.spawn(cmd, logfile=stl)

    #################################################
    # Logging into VyOS system
    #################################################
    try:
        c.expect('Automatic boot in', timeout=10)
        c.sendline('')
    except pexpect.TIMEOUT:
        print("\n#  Did not find grub countdown window, ignoring")
    
    c.expect('[Ll]ogin:', timeout=120)
    c.sendline('vyos')
    c.expect('[Pp]assword:', timeout=10)
    c.sendline('vyos')
    c.expect('vyos@vyos:~\$')

    #################################################
    # Installing into VyOS system
    #################################################
    c.sendline('install image')
    c.expect('\nWould you like to continue?.*:')
    c.sendline('yes')
    c.expect('\nPartition.*:')
    c.sendline('')
    c.expect('\nInstall the image on.*:')
    c.sendline('')
    c.expect('\nContinue\?.*:')
    c.sendline('Yes')
    c.expect('\nHow big of a root partition should I create?.*:')
    c.sendline('')
    c.expect('\nWhat would you like to name this image?.*:')
    c.sendline('')
    c.expect('\nWhich one should I copy to.*:', timeout=300)
    c.sendline('')
    c.expect('\nEnter password for user.*:')
    c.sendline('vyos')
    c.expect('\nRetype password for user.*:')
    c.sendline('vyos')
    c.expect('\nWhich drive should GRUB modify the boot partition on.*:')
    c.sendline('')
    c.expect('\nvyos@vyos:~\$')

    #################################################
    # Powering down installer
    #################################################
    c.sendline('poweroff')
    c.expect('\nAre you sure you want to poweroff this system.*\]')
    c.sendline('Y')
    print("# Shutting down virtual machine")
    for i in range(30):
        print("# Waiting...")
        if not c.isalive():
            print("# VM is shut down!")
            break;
        time.sleep(10) 
    else:
        print("# VM Did not shut down after 300sec")
    c.close()


    #################################################
    # Booting installed system
    #################################################
    print("\n\n\n")
    print("#"*80)
    print("# Booting ")
    print("#"*80)

    cmd = """qemu-system-x86_64 \
    -name "TESTVM" \
    -m 1G \
    -nic user,model=virtio,mac=52:54:99:12:34:56,hostfwd=tcp::2299-:22
    -machine accel=kvm \
    -cpu host -smp 2 \
    -vnc 0.0.0.0:99 \
    -nographic \
    -drive format=raw,file={DISK}
    """.format(DISK=args.disk)

    print("Executing command: {}".format(cmd))
    c = pexpect.spawn(cmd, logfile=log)

    #################################################
    # Logging into VyOS system
    #################################################
    try:
        c.expect('The highlighted entry will be executed automatically in', timeout=10)
        c.sendline('')
    except pexpect.TIMEOUT:
        print("\n#  Did not find grub countdown window, ignoring")

    c.expect('[Ll]ogin:', timeout=120)
    c.sendline('vyos')
    c.expect('[Pp]assword:', timeout=10)
    c.sendline('vyos')

    c.expect('vyos@vyos:~\$')


    #################################################
    # Executing test-suite
    #################################################
    print("\n\n\n")
    print("#"*80)
    print("# Executing test-suite ")
    print("#"*80)

    def cr(child, command):
        child.sendline(command)
        i = child.expect(['\n +Invalid command:', 
                        '\n +Set failed', 
                        'No such file or directory', 
                        '\n\S+@\S+[$#]'])

        if i==0:
            raise Exception('Invalid command detected')
        elif i==1:
            raise Exception('Set syntax failed :/')
        elif i==2:
            print("# WTF? did not find VyOS-smoketest, this should be an exception")
            #raise Exception("WTF? did not find VyOS-smoketest, this should be an exception")
    cr(c, '/usr/bin/vyos-smoketest')

    print("\n\n\n")
    print("#"*80)
    print("# Smoke test status")
    print("#"*80)
    data = c.before.decode()

    #################################################
    # Powering off system
    #################################################
    print("\n\n\n")
    print("#"*80)
    print("# Booting ")
    print("#"*80)
    c.sendline('poweroff')
    c.expect('\nAre you sure you want to poweroff this system.*\]')
    c.sendline('Y')
    print("# Shutting down virtual machine")
    for i in range(30):
        print("# Waiting...")
        if not c.isalive():
            print("# VM is shut down!")
            break;
        time.sleep(10) 
    else:
        raise Exception("VM Did not shut down after 300sec")
    c.close()

except pexpect.exceptions.TIMEOUT:
    print("Timeout waiting for VyOS system")
    traceback.print_exc()
    EXCEPTION = 1

except pexpect.exceptions.ExceptionPexpect:
    print("Exeption while executing QEMU")
    print("Is qemu working on this system?")
    traceback.print_exc()
    EXCEPTION = 1

except Exception:
    print("An unknown error occured when installing the VyOS system")
    print("Traceback: ")
    traceback.print_exc()
    EXCEPTION = 1



#################################################
# Cleaning up
#################################################
print("\n\n\n")
print("#"*80)
print("# Cleaning up")
print("#"*80)

if not args.keep:
    print("Removing disk file: {}".format(args.disk))
    try:
        os.remove(args.disk)
    except Exception:
        print("Exception while removing diskimage")
        traceback.print_exc()
        EXCEPTION = 1

if EXCEPTION:
    print("")
    print("Hmm...")
    print("System got an exception while processing")
    print("The ISO is not considered usable")
    sys.exit(1)