# TODO: imports
from diyhue.bridge.config import BridgeConfig
from diyhue.bridge.emulator import BridgeEmulator
from diyhue.bridge.utils import get_mac, get_ip

import os
from pathlib import Path
_DEFAULT_CONFIG_FILE = '{}/.diyhue/config.json'.format(str(Path.home()))
print('_DEFAULT_CONFIG_FILE: {}'.format(_DEFAULT_CONFIG_FILE))

def start(*args, **kwargs):
    if 'filename' in kwargs:
        filename = kwargs['filename']
    else:
        #default filename for config
        filename = _DEFAULT_CONFIG_FILE
    # get IP and mac
    ip = get_ip()
    mac = get_mac()

    # Make config 
    bridge_config = BridgeConfig(filename=filename,
                                    ip=ip,
                                    mac=mac)
    bridge_config.update()

    # create emulator, pass in config
    bridge_emulator = BridgeEmulator(bridge_config)

    # wait for threads to join, catch exceptions
    try:
        # bridge_emulator.start()
        bridge_emulator.join_all()
    except Exception as e:
        # TODO: on exception, spawn thread to save config backup
        print('[Main] Exception waiting on join: {}'.format(e))
    finally:
        # Clean up, save config
        run_service = False
        # bridge_config.save()
        print('[Main] Config saved')