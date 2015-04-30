from setuptools import setup
from subprocess import check_call, call
import logging
from setuptools.command.develop import develop
from setuptools.command.install import install


def parcel_build(command_subclass):
    original = command_subclass.run

    def parcel_run(self):
        try:
            call(['make', 'clean'])
            check_call(['make'])
        except Exception as e:
            logging.error(
                "Unable to build UDT library: {}".format(e))
        else:
            original(self)

    command_subclass.run = parcel_run
    return command_subclass


@parcel_build
class ParcelInstall(install):
    pass


@parcel_build
class ParcelDevelop(develop):
    pass


setup(
    name='parcel',
    packages=["parcel"],
    cmdclass={
        'install': ParcelInstall,
        'develop': ParcelDevelop,
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
