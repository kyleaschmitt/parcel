from setuptools import setup
from distutils.command.install import install as DistutilsInstall
from subprocess import check_call, call
import logging


class ParcelInstall(DistutilsInstall):

    def run(self):
        try:
            call(['make', 'clean'])
            check_call(['make'])
        except Exception as e:
            logging.error(
                "Unable to build UDT library: {}".format(e))
        else:
            DistutilsInstall.run(self)

setup(
    name='parcel',
    packages=["parcel"],
    cmdclass={
        'install': ParcelInstall,
    },
    install_requires=[
        'requests==2.6.0',
        'progressbar==2.3',
        'Flask==0.10.1',
        'intervaltree==2.0.4',
    ],
    package_data={
        "parcel": [
            "src/lparcel.so",
        ]
    },
    scripts=[
        'bin/parcel',
        'bin/parcel-server',
        'bin/parcel-tcp2udt',
        'bin/parcel-udt2tcp',
    ]
)
