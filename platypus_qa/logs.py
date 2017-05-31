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
import json


class DictLogger:
    def log(self, data):
        raise NotImplementedError('RequestLogger.log is not implemented')


class DummyDictLogger(DictLogger):
    def log(self, data):
        pass


class JsonFileDictLogger(DictLogger):
    def __init__(self, file_name):
        self._file_name = file_name

    def log(self, data):
        with open(self._file_name, 'at') as fp:
            fp.write(json.dumps(data))
            fp.write('\n')
