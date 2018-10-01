# Python README

## Setup

1. Install venv `sudo apt-get install python3-venv`
2. Make main directory `mkdir ~/.diyhue && cd ~/.diyhue`
3. Create venv `python3 -m venv diyhue`
4. Activate venv `source diyhue/bin/activate`
5. Clone diyhue `cd ~ && git clone https://github.com/maxakuru/diyHue.git`
6. Install diyhue `cd diyHue/python` `sudo ~/.diyhue/diyhue/bin/python3 setup.py install`
7. If needed, change diy start script `sudo nano ~/.diyhue/diyhue/bin/diy` change python path on first line to `#!~/.diyhue/diyhue/bin/python3` and exit `ctrl+x`
8. Start diyHue as root `sudo diy start`
