from setuptools import setup

setup(
    name='parcel',
    packages=["parcel"],
    install_requires=[
        'requests',
        'progressbar==2.2',
    ],
    scripts=[
        'bin/parcel',
        'bin/parcel-server'
    ]
)
