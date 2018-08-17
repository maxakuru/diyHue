# TODO: imports

# TODO: load config

updateConfig()
if bridge_config["deconz"]["enabled"]:
    scanDeconz()
try:
    if update_lights_on_startup:
        updateAllLights()
    Thread(target=ssdpSearch, args=[getIpAddress(), mac]).start()
    Thread(target=ssdpBroadcast, args=[getIpAddress(), mac]).start()
    Thread(target=schedulerProcessor).start()
    Thread(target=syncWithLights).start()
    Thread(target=entertainmentService).start()
    Thread(target=run, args=[False]).start()
    Thread(target=run, args=[True]).start()
    Thread(target=daylightSensor).start()
    while True:
        sleep(10)
except Exception as e:
    print("server stopped " + str(e))
finally:
    run_service = False
    saveConfig()
    print ('config saved')