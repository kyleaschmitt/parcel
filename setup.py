from setuptools import setup

setup(
    name='parcel',
    packages=["parcel"],
    install_requires=[
        'voluptuous',
    ],
    scripts=[
        'bin/parcel',
        'bin/parcel-server'
    ]
)
