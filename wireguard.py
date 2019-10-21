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

            output[device] = {
                'private_key': None if private_key == '(none)' else private_key,
                'public_key': None if public_key == '(none)' else public_key,
                'listen_port': int(listen_port),
                'fw_mark': None if fw_mark == 'off' else int(fw_mark),
                'peers': {},
                } 
        else:
            # We are entering a peer
            device, public_key, preshared_key, endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx, persistent_keepalive = items
            output[device][public_key] = {
                'preshared_key': None if preshared_key == '(none)' else preshared_key,
                'endpoint': None if endpoint == '(none)' else endpoint,
                'allowed_ips': allowed_ips.split(','),
                'latest_handshake': None if latest_handshake == '0' else int(latest_handshake),
                'transfer_rx': int(transfer_rx),
                'transfer_tx': int(transfer_tx),
                'persistent_keepalive': None if persistent_keepalive == 'off' else int(persistent_keepalive),
           } 
    return output
            
if __name__ == "__main__":
    import json
    print(json.dumps(wireguard_dump(), indent=4))
