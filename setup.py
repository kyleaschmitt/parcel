from setuptools import setup

setup(
    name='parcel',
    packages=["parcel"],
    install_requires=[
        'requests==2.5.1',
    ],
    scripts=[
        'bin/parcel',
        'bin/parcel-server'
    ]
)
