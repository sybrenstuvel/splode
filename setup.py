#!/usr/bin/env python

import setuptools

setuptools.setup(
    name='splode',
    version='0.1',
    packages=setuptools.find_packages('.', exclude=['test']),
    install_requires=[
        'blender-bam>=1.0',
    ],
    zip_safe=False,
    entry_points={'console_scripts': [
        'bls = splode_cli.blendfile_ls:main',
    ]},
)
