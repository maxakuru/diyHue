from setuptools import setup

with open('README.md') as readme_file:
    readme = readme_file.read()

required = []

setup(
    name='diyHue',
    version='0.1.0',
    description='',
    long_description=readme,
    packages=[  'diyhue',
                'diyhue.utils',
                'diyhue.nginx',
                'diyhue.config',
                'diyhue.bridge'
                ],
    install_requires=required,
    entry_points = {
        'console_scripts': ['diy=TODO']
    }
)