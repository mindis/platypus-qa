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

import unittest

from platypus_qa.nlp.universal_dependencies import UDDependency


class _UDDependencyTest(unittest.TestCase):
    def test_eq(self):
        self.assertEquals(UDDependency.acl, UDDependency.acl)
        self.assertNotEquals(UDDependency.acl, UDDependency.advcl)
        self.assertNotEqual(UDDependency.acl_relcl, UDDependency.acl)
        self.assertNotEqual(UDDependency.acl, UDDependency.acl_relcl)
        self.assertEqual(UDDependency.acl_relcl, UDDependency.acl_relcl)

    def test_le(self):
        self.assertTrue(UDDependency.acl <= UDDependency.acl)
        self.assertTrue(UDDependency.acl_relcl <= UDDependency.acl)
        self.assertFalse(UDDependency.acl <= UDDependency.acl_relcl)
        self.assertFalse(UDDependency.acl_relcl <= UDDependency.advcl)

    def test_lt(self):
        self.assertFalse(UDDependency.acl < UDDependency.acl)
        self.assertTrue(UDDependency.acl_relcl < UDDependency.acl)
        self.assertFalse(UDDependency.acl < UDDependency.acl_relcl)
        self.assertFalse(UDDependency.acl_relcl < UDDependency.advcl)

    def test_ge(self):
        self.assertTrue(UDDependency.acl >= UDDependency.acl_relcl)
        self.assertTrue(UDDependency.acl_relcl >= UDDependency.acl_relcl)
        self.assertFalse(UDDependency.acl_relcl >= UDDependency.acl)
        self.assertFalse(UDDependency.advcl >= UDDependency.acl_relcl)

    def test_gt(self):
        self.assertFalse(UDDependency.acl > UDDependency.acl)
        self.assertTrue(UDDependency.acl > UDDependency.acl_relcl)
        self.assertFalse(UDDependency.acl_relcl > UDDependency.acl)
        self.assertFalse(UDDependency.advcl > UDDependency.acl_relcl)
