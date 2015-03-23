from setuptools import setup

setup(
    name='parcel',
    packages=["parcel"],
    install_requires=[
        'requests==2.6.0',
        'progressbar==2.2',
    ],
    scripts=[
        'bin/parcel',
        'bin/parcel-server'
    ]
)
