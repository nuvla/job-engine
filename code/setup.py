# -*- coding: utf-8 -*-
import sys

from setuptools import find_packages, setup

with open('requirements.txt') as f:
    install_requires = []
    for line in f.readlines():
        if not line.startswith('mock'):
            install_requires.append(line)

if sys.version_info < (3, 2):
    install_requires.append('configparser')

version = '${project.version}'
packages = find_packages(where='src/')

setup(
    name='nuvla-job-engine',
    version=version,
    author="SixSq Sarl",
    author_email='support@sixsq.com',
    url='http://sixsq.com/slipstream',
    description="Nuvla Job Engine.",
    keywords='nuvla devops job engine',
    package_dir={'': 'src'},
    packages=packages,
    namespace_packages=['nuvla'],
    zip_safe=False,
    license='Apache License, Version 2.0',
    include_package_data=True,
    install_requires=install_requires,
    classifiers=[
        'Development Status :: 4 - Betta',
        'License :: OSI Approved :: Apache Software License',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development'
    ],
)