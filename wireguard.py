#!/usr/bin/env python3
import subprocess


def wireguard_dump():
    _f = subprocess.check_output(["wg", "show", "all", "dump"])
    last_device=None
    output = {}
    for line in _f.decode().split('\n'):
        if not line:
          # Skip empty lines and last line
          continue
        items = line.split('\t')

        if last_device != items[0]:
            last_device = items[0]
            # We are currently entering a new node
            device, private_key, public_key, listen_port, fw_mark = items
            if private_key == '(none)':
                private_key = None
            if public_key == '(none)':
                public_key = None
            listen_port = int(listen_port)
            if fw_mark == 'off':
                fw_mark = None
            else:
                fw_mark = int(fw_mark)

            output[items[0]] = {
                'private_key': private_key,
                'public_key': public_key,
                'listen_port': listen_port,
                'fw_mark': fw_mark,
                'peers': {},
                } 
        else:
            # We are entering a peer
            device, public_key, preshared_key, endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx, persistent_keepalive = items
            if preshared_key == '(none)':
                preshared_key = None
            if endpoint == '(none)':
                endpoint = None
            if latest_handshake == '0':
                latest_handshake = None
            else:
                latest_handshake = int(latest_handshake)
            transfer_rx = int(transfer_rx)
            transfer_tx = int(transfer_tx)
            if persistent_keepalive == 'off':
                persistent_keepalive = None
            else:
                persistent_keepalive = int(persistent_keepalive)
            allowed_ips = allowed_ips.split(',')
            output[device][public_key] = {
                'preshared_key': preshared_key,
                'endpoint': endpoint,
                'allowed_ips': allowed_ips,
                'latest_handshake': latest_handshake,
                'transfer_rx': transfer_rx,
                'transfer_tx': transfer_tx,
                'persistent_keepalive': persistent_keepalive,
           } 

    return output
            


if __name__ == "__main__":
    import json
    print(json.dumps(wireguard_dump(), indent=4))
