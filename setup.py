from setuptools import setup

setup(
    name='parcel',
    packages=["parcel"],
    install_requires=[
        'requests==2.6.0',
        'progressbar==2.3',
        'Flask==0.10.1',
        'intervaltree==2.0.4',
    ],
    scripts=[
        'bin/parcel',
        'bin/parcel-server',
        'bin/parcel-tcp2udt',
        'bin/parcel-udt2tcp',
    ]
)
