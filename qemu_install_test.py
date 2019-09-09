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
parser.add_argument('--silent', help='Do not show output on stdout unless an error has occured', 
                              action='store_true',
                              default=False)   
parser.add_argument('--debug', help='Send all debug output to stdout',
                               action='store_true', 
                               default=False)                      
parser.add_argument('--logfile', help='Log to file')  

args = parser.parse_args()

class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = b''
        self.ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')

    def write(self, buf):
        self.linebuf += buf
        #print('.')
        while b'\n' in self.linebuf:
            f = self.linebuf.split(b'\n', 1)
            if len(f) == 2:
                self.logger.debug(self.ansi_escape.sub('', f[0].decode(errors="replace").rstrip()))
                self.linebuf = f[1]
            #print(f)


    def flush(self):
        pass


# Setting up logger
log = logging.getLogger()
log.setLevel(logging.DEBUG)

stl = StreamToLogger(log)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

handler = logging.StreamHandler(sys.stdout)
if args.silent:
    handler.setLevel(logging.ERROR)
elif args.debug:
    handler.setLevel(logging.DEBUG)
else:
    handler.setLevel(logging.INFO)

handler.setFormatter(formatter)
log.addHandler(handler)


if args.logfile:
    filehandler = logging.FileHandler(args.logfile)
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(formatter)
    log.addHandler(filehandler)



if args.silent:
    output = BytesIO()
else:
    output = sys.stdout.buffer

if not os.path.isfile(args.iso):
    log.error("Unable to find iso image to install")
    sys.exit(1)


# Creating diskimage!!

if not os.path.isfile(args.disk):
    log.info("Creating Disk image {}".format(args.disk))
    c = subprocess.check_output(["qemu-img", "create", args.disk, "2G"])
    log.debug(c.decode())
else:
    log.info("Diskimage already exists, using the existing one")



try:
    #################################################
    # Installing image to disk
    #################################################
    log.info("Installing system")

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
    log.debug("Executing command: {}".format(cmd))
    c = pexpect.spawn(cmd, logfile=stl)

    #################################################
    # Logging into VyOS system
    #################################################
    try:
        c.expect('Automatic boot in', timeout=10)
        c.sendline('')
    except pexpect.TIMEOUT:
        log.warning("Did not find grub countdown window, ignoring")

    log.info('Waiting for login prompt')
    c.expect('[Ll]ogin:', timeout=120)
    c.sendline('vyos')
    c.expect('[Pp]assword:', timeout=10)
    c.sendline('vyos')
    c.expect('vyos@vyos:~\$')
    log.info('Logged in!')


    #################################################
    # Installing into VyOS system
    #################################################
    log.info("Starting installer")
    c.sendline('install image')
    c.expect('\nWould you like to continue?.*:')
    c.sendline('yes')
    log.info("Partitioning disk")
    c.expect('\nPartition.*:')
    c.sendline('')
    c.expect('\nInstall the image on.*:')
    c.sendline('')
    c.expect('\nContinue\?.*:')
    c.sendline('Yes')
    c.expect('\nHow big of a root partition should I create?.*:')
    c.sendline('')
    log.info('Disk partitioned, installing')
    c.expect('\nWhat would you like to name this image?.*:')
    c.sendline('')
    log.info('Copying files')
    c.expect('\nWhich one should I copy to.*:', timeout=300)
    c.sendline('')
    log.info('Files Copied!')
    c.expect('\nEnter password for user.*:')
    c.sendline('vyos')
    c.expect('\nRetype password for user.*:')
    c.sendline('vyos')
    c.expect('\nWhich drive should GRUB modify the boot partition on.*:')
    c.sendline('')
    c.expect('\nvyos@vyos:~\$')
    log.info('system installed, shutting down')

    #################################################
    # Powering down installer
    #################################################
    log.info("Shutting down installation system")
    c.sendline('poweroff')
    c.expect('\nAre you sure you want to poweroff this system.*\]')
    c.sendline('Y')
    for i in range(30):
        log.info("Waiting for shutdown...")
        if not c.isalive():
            log.info("VM is shut down!")
            break;
        time.sleep(10) 
    else:
        log.error("VM Did not shut down after 300sec, killing")
    c.close()


    #################################################
    # Booting installed system
    #################################################
    log.info("Booting installed system")

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

    log.debug('Executing command: {}'.format(cmd))
    c = pexpect.spawn(cmd, logfile=stl)

    #################################################
    # Logging into VyOS system
    #################################################
    try:
        c.expect('The highlighted entry will be executed automatically in', timeout=10)
        c.sendline('')
    except pexpect.TIMEOUT:
        log.warning("Did not find grub countdown window, ignoring")

    log.info('Waiting for login prompt')
    c.expect('[Ll]ogin:', timeout=120)
    c.sendline('vyos')
    c.expect('[Pp]assword:', timeout=10)
    c.sendline('vyos')
    c.expect('vyos@vyos:~\$')
    log.info('Logged in!')



    #################################################
    # Executing test-suite
    #################################################
    log.info("Executing test-suite ")

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
            log.error("Did not find VyOS-smoketest, this should be an exception")
            #raise Exception("WTF? did not find VyOS-smoketest, this should be an exception")
    cr(c, '/usr/bin/vyos-smoketest')

    log.info("Smoke test status")
    #data = c.before.decode()

    #################################################
    # Powering off system
    #################################################
    log.info("Powering off system ")
    c.sendline('poweroff')
    c.expect('\nAre you sure you want to poweroff this system.*\]')
    c.sendline('Y')
    log.info("Shutting down virtual machine")
    for i in range(30):
        log.info("Waiting for shutdown...")
        if not c.isalive():
            log.info("VM is shut down!")
            break;
        time.sleep(10) 
    else:
        log.error("VM Did not shut down after 300sec")
        raise Exception("VM Did not shut down after 300sec")
    c.close()

except pexpect.exceptions.TIMEOUT:
    log.error("Timeout waiting for VyOS system")
    log.error(traceback.format_exc())
    EXCEPTION = 1

except pexpect.exceptions.ExceptionPexpect:
    log.error("Exeption while executing QEMU")
    log.error("Is qemu working on this system?")
    log.error(traceback.format_exc())
    EXCEPTION = 1

except Exception:
    log.error("An unknown error occured when installing the VyOS system")
    traceback.print_exc()
    EXCEPTION = 1



#################################################
# Cleaning up
#################################################
log.info("Cleaning up")

if not args.keep:
    log.info("Removing disk file: {}".format(args.disk))
    try:
        os.remove(args.disk)
    except Exception:
        log.error("Exception while removing diskimage")
        log.error(traceback.format_exc())
        EXCEPTION = 1

if EXCEPTION:
    log.error("Hmm... System got an exception while processing")
    log.error("The ISO is not considered usable")
    sys.exit(1)