from setuptools import setup

setup(
    name='parcel',
    packages=["parcel"],
    install_requires=[
        'requests',
    ],
    scripts=[
        'bin/parcel',
        'bin/parcel-server'
    ]
)
