# TODO: imports
from diyhue.bridge.config import BridgeConfig
from diyhue.bridge.emulator import BridgeEmulator
from diyhue.bridge.utils import get_mac, get_ip

def start(*args, **kwargs):
    # get IP and mac
    ip = get_ip()
    mac = get_mac()

    # Make config 
    bridge_config = BridgeConfig(filename=(kwargs['filename'] or '/opt/hue-emulator/config.json'),
                                    ip=ip,
                                    mac=mac)
    bridge_config.update_config()

    # create emulator, pass in config
    bridge_emulator = BridgeEmulator(bridge_config)

    # wait for threads to join, catch exceptions
    try:
        bridge_emulator.start()
        bridge_emulator.join_all()
    except Exception as e:
        # TODO: on exception, spawn thread to save config backup
        print('[Main] Exception waiting on join: {}'.format(e))
    finally:
        # Clean up, save config
        run_service = False
        bridge_config.save()
        print('[Main] Config saved')