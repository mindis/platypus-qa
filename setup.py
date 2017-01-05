#!/usr/bin/env python3
# coding=utf-8
"""
Copyright (c) 2017 Lexistems SAS and École normale supérieure de Lyon

This file is part of Platypus.

Platypus is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

from setuptools import setup, find_packages
from setuptools.command.install import install


class CustomInstall(install):
    def run(self):
        install.run(self)

        import nltk
        nltk.download('wordnet')
        nltk.download('omw')


setup(
    name='platypus_qa',
    version='0.0.1',
    description='Platypus QA system',
    url='https://github.com/askplatypus',
    classifiers=[
        'Environment :: No Input/Output (Daemon)',
        'Framework :: Flask',
        'Development Status :: 1 - Planning',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Natural Language :: English',
        'Natural Language :: French',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application'
    ],
    install_requires=[
        'requests',
        'ppp_datamodel>=0.6.11',
        'nltk',
        'dateparser',
        'ppp_cas',
        'langdetect',
        'PyLD',
        'Flask',
        'flask-swaggerui>=0.0.1',
        'flask-cors>=3.0<4.0'
    ],
    setup_requires=['nltk'],
    packages=find_packages(),
    cmdclass={'install': CustomInstall},
    test_suite='tests'
)
