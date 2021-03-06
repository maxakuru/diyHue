from setuptools import setup
import subprocess

with open('README.md') as readme_file:
    readme = readme_file.read()

required = []

print('in here')
subprocess.call(['./gen_cert.sh'])

setup(
    name='diyHue',
    version='0.1.0',
    description='',
    long_description=readme,
    packages=[  'diyhue',
                'diyhue.cli',
                'diyhue.bridge.utils',
                'diyhue.bridge.utils.logging',
                'diyhue.bridge',
                'diyhue.bridge.server',
                'diyhue.bridge.config',
                'diyhue.bridge.emulator',
                'diyhue.bridge.emulator.controllers',
                'diyhue.bridge.emulator.controllers.deconz',
                'diyhue.bridge.emulator.controllers.entertainment',
                'diyhue.bridge.emulator.controllers.hue',
                'diyhue.bridge.emulator.controllers.scheduler',
                'diyhue.bridge.emulator.controllers.ssdp',
                'diyhue.bridge.emulator.protocols'
                ],
    package_data= {
                    'diyhue.bridge.server': ['cert.pem', 'nginx.conf']
                    },
    install_requires=required,
    entry_points = {
        'console_scripts': ['diy=diyhue.cli.main:main']
    }
)