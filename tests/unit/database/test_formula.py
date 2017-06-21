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

from platypus_qa.database.formula import *
from platypus_qa.database.owl import *

_x = VariableFormula('x')
_y = VariableFormula('y')
_foo = ValueFormula(XSDStringLiteral("foo"))
_bar = ValueFormula(XSDStringLiteral("bar"))
_false = ValueFormula(XSDBooleanLiteral(False))
_0 = ValueFormula(XSDDecimalLiteral(Decimal(0)))
_1 = ValueFormula(XSDDecimalLiteral(Decimal(1)))
_2 = ValueFormula(XSDDecimalLiteral(Decimal(2)))
_2016 = ValueFormula(XSDDateTimeLiteral(2016, 0, 0, 0, 0, 0))
_schema_name = ValueFormula(DatatypeProperty('http://schema.org/name', schema_Person, xsd_string))
_JohnDoe = ValueFormula(NamedIndividual('http://example.com/me', (schema_Person,)))


class _FormulaTest(unittest.TestCase):
    def testType(self):
        self.assertEqual(Type.bottom(), Type.from_entity(owl_Nothing))
        self.assertEqual(Type.top(), Type.from_entity(owl_Thing) | Type.from_entity(rdfs_Literal))
        self.assertEqual(Type.bottom(), Type.bottom() & Type.bottom())
        self.assertEqual(Type.bottom(), Type.bottom() | Type.bottom())

        self.assertEqual(Type.from_entity(schema_Person),
                         Type.from_entity(owl_Thing) & Type.from_entity(schema_Person))
        self.assertEqual(Type.from_entity(owl_Thing), Type.from_entity(owl_Thing) | Type.from_entity(schema_Person))
        self.assertEqual(Type.bottom(), Type.from_entity(owl_Thing) & Type.from_entity(owl_Nothing))
        self.assertEqual(Type.from_entity(owl_Thing), Type.from_entity(owl_Thing) | Type.from_entity(owl_Nothing))

        self.assertEqual(Type.from_entity(xsd_string), Type.from_entity(rdfs_Literal) & Type.from_entity(xsd_string))
        self.assertEqual(Type.from_entity(rdfs_Literal), Type.from_entity(rdfs_Literal) | Type.from_entity(xsd_string))
        self.assertEqual(Type.bottom(), Type.from_entity(xsd_decimal) & Type.from_entity(xsd_string))

        self.assertGreater(Type.top(), Type.bottom())
        self.assertGreater(Type.from_entity(owl_Thing), Type.from_entity(schema_Person))
        self.assertGreater(Type.from_entity(rdfs_Literal), Type.from_entity(xsd_string))
        self.assertGreater(Type.from_entity(xsd_string) | Type.from_entity(xsd_decimal), Type.from_entity(xsd_decimal))

        self.assertGreaterEqual(Type.top(), Type.bottom())
        self.assertGreaterEqual(Type.from_entity(owl_Thing), Type.from_entity(schema_Person))
        self.assertGreaterEqual(Type.from_entity(rdfs_Literal), Type.from_entity(xsd_string))
        self.assertGreaterEqual(Type.from_entity(xsd_string) | Type.from_entity(xsd_decimal),
                                Type.from_entity(xsd_decimal))
        self.assertGreaterEqual(Type.from_entity(xsd_string), Type.from_entity(xsd_string))
        self.assertGreaterEqual(Type.from_entity(schema_Person), Type.from_entity(schema_Person))

        self.assertLess(Type.bottom(), Type.top())
        self.assertLess(Type.from_entity(schema_Person), Type.from_entity(owl_Thing))
        self.assertLess(Type.from_entity(xsd_string), Type.from_entity(rdfs_Literal))
        self.assertLess(Type.from_entity(xsd_decimal), Type.from_entity(xsd_string) | Type.from_entity(xsd_decimal))

        self.assertLessEqual(Type.bottom(), Type.top())
        self.assertLessEqual(Type.from_entity(schema_Person), Type.from_entity(owl_Thing))
        self.assertLessEqual(Type.from_entity(xsd_string), Type.from_entity(rdfs_Literal))
        self.assertLessEqual(Type.from_entity(xsd_decimal),
                             Type.from_entity(xsd_string) | Type.from_entity(xsd_decimal))
        self.assertLessEqual(Type.from_entity(xsd_string), Type.from_entity(xsd_string))
        self.assertLessEqual(Type.from_entity(schema_Person), Type.from_entity(schema_Person))

        self.assertEqual(Type.bottom(), owl_Nothing)
        self.assertGreater(Type.top(), owl_Thing)
        self.assertGreaterEqual(Type.top(), owl_Thing)
        self.assertLess(Type.bottom(), owl_Thing)
        self.assertLessEqual(Type.bottom(), owl_Nothing)

    def testValueFormula(self):
        self.assertEqual(Type.from_entity(schema_Person),
                         ValueFormula(NamedIndividual('wd:Q42', (schema_Person,))).type)
        self.assertEqual(Type.from_entity(xsd_string), ValueFormula(XSDStringLiteral('foo')).type)
        self.assertTrue(true_formula)
        self.assertFalse(false_formula)

    def testEqualityFormula(self):
        self.assertEqual(EqualityFormula(_x, _y), EqualityFormula(_x, _y))
        self.assertEqual(EqualityFormula(_x, _y), EqualityFormula(_y, _x))
        self.assertNotEqual(EqualityFormula(_x, _y), EqualityFormula(_x, _foo))
        self.assertEqual(true_formula, EqualityFormula(_x, _x))
        self.assertEqual(true_formula, EqualityFormula(_foo, _foo))
        self.assertEqual(false_formula, EqualityFormula(_foo, _bar))

    def testPlusFormula(self):
        self.assertEqual(AddFormula(_1, _2), _1 + _2)
        self.assertEqual(AddFormula(_1, _2), AddFormula(_2, _1))
        with self.assertRaises(ValueError):
            AddFormula(_1, _foo)
        with self.assertRaises(ValueError):
            AddFormula(_foo, _1)

    def testSubFormula(self):
        self.assertEqual(SubFormula(_1, _2), _1 - _2)
        with self.assertRaises(ValueError):
            SubFormula(_1, _foo)
        with self.assertRaises(ValueError):
            SubFormula(_foo, _1)

    def testMulFormula(self):
        self.assertEqual(MulFormula(_1, _2), _1 * _2)
        self.assertEqual(MulFormula(_1, _2), MulFormula(_2, _1))
        with self.assertRaises(ValueError):
            MulFormula(_1, _foo)
        with self.assertRaises(ValueError):
            MulFormula(_foo, _1)

    def testDivFormula(self):
        self.assertEqual(DivFormula(_1, _2), _1 / _2)
        with self.assertRaises(ValueError):
            DivFormula(_1, _foo)
        with self.assertRaises(ValueError):
            DivFormula(_foo, _1)

    def testAndFormula(self):
        self.assertEqual(true_formula, AndFormula([]))
        self.assertEqual(false_formula, AndFormula([false_formula]))
        self.assertEqual(EqualityFormula(_x, _x), EqualityFormula(_x, _x) & true_formula)
        self.assertEqual(
            EqualityFormula(_x, _x) & EqualityFormula(_y, _y),
            EqualityFormula(_x, _x) & AndFormula([EqualityFormula(_y, _y)])
        )
        self.assertEqual(
            (TripleFormula(_x, _schema_name, _foo) & EqualityFormula(_y, _y)) |
            (TripleFormula(_x, _schema_name, _bar) & EqualityFormula(_y, _y)),
            (TripleFormula(_x, _schema_name, _foo) | TripleFormula(_x, _schema_name, _bar)) & EqualityFormula(_y, _y)
        )
        self.assertEqual(
            (TripleFormula(_x, _schema_name, _foo) & EqualityFormula(_y, _y)) |
            (TripleFormula(_x, _schema_name, _bar) & EqualityFormula(_y, _y)),
            EqualityFormula(_y, _y) & (TripleFormula(_x, _schema_name, _foo) | TripleFormula(_x, _schema_name, _bar))
        )

    def testOrFormula(self):
        self.assertEqual(false_formula, OrFormula([]))
        self.assertEqual(true_formula, AndFormula([true_formula]))
        self.assertEqual(EqualityFormula(_x, _x), EqualityFormula(_x, _x) | false_formula)
        self.assertEqual(
            EqualityFormula(_x, _x) | EqualityFormula(_y, _y),
            EqualityFormula(_x, _x) | OrFormula([EqualityFormula(_y, _y)])
        )

    def testNotFormula(self):
        self.assertEqual(false_formula, NotFormula(true_formula))
        self.assertEqual(true_formula, ~ false_formula)
        self.assertEqual(EqualityFormula(_x, _x), ~ ~ EqualityFormula(_x, _x))
        self.assertEqual(
            ~ EqualityFormula(_x, _x) | ~ EqualityFormula(_y, _y),
            ~ (EqualityFormula(_x, _x) & EqualityFormula(_y, _y))
        )
        self.assertEqual(
            ~ EqualityFormula(_x, _x) & ~ EqualityFormula(_y, _y),
            ~ (EqualityFormula(_x, _x) | EqualityFormula(_y, _y))
        )

    def testGreaterFormula(self):
        self.assertEqual(GreaterFormula(_1, _2), _1 > _2)
        with self.assertRaises(ValueError):
            GreaterFormula(_1, _foo)
        with self.assertRaises(ValueError):
            GreaterFormula(_foo, _1)

    def testGreaterOrEqualFormula(self):
        self.assertEqual(GreaterOrEqualFormula(_1, _2), _1 >= _2)
        with self.assertRaises(ValueError):
            GreaterOrEqualFormula(_1, _foo)
        with self.assertRaises(ValueError):
            GreaterOrEqualFormula(_foo, _1)

    def testLowerFormula(self):
        self.assertEqual(LowerFormula(_1, _2), _1 < _2)
        with self.assertRaises(ValueError):
            LowerFormula(_1, _foo)
        with self.assertRaises(ValueError):
            LowerFormula(_foo, _1)

    def testLowerOrEqualFormula(self):
        self.assertEqual(LowerOrEqualFormula(_1, _2), _1 <= _2)
        with self.assertRaises(ValueError):
            LowerOrEqualFormula(_1, _foo)
        with self.assertRaises(ValueError):
            LowerOrEqualFormula(_foo, _1)

    def testExistsFormula(self):
        self.assertEqual(ExistsFormula(_x, TripleFormula(_x, _schema_name, _foo)),
                         ExistsFormula(_y, TripleFormula(_y, _schema_name, _foo)))
        self.assertEqual(true_formula, ExistsFormula(_y, true_formula))
        self.assertEqual(false_formula, ExistsFormula(_y, false_formula))
        self.assertEqual(
            ExistsFormula(_x, TripleFormula(_x, _schema_name, _foo)) |
            ExistsFormula(_x, TripleFormula(_x, _schema_name, _bar)),
            ExistsFormula(_x, TripleFormula(_x, _schema_name, _foo) | TripleFormula(_x, _schema_name, _bar))
        )
        self.assertEqual(true_formula, ExistsFormula(_x, EqualityFormula(_x, _foo)))
        self.assertEqual(
            TripleFormula(_x, _schema_name, _foo),
            ExistsFormula(_y, TripleFormula(_x, _schema_name, _y) & EqualityFormula(_y, _foo))
        )
        self.assertEqual(
            TripleFormula(_x, _schema_name, _foo),
            ExistsFormula(_y, TripleFormula(_x, _schema_name, _y) & EqualityFormula(_foo, _y))
        )
        self.assertEqual(
            TripleFormula(_x, _schema_name, _foo),
            ExistsFormula(_y, TripleFormula(_y, _schema_name, _foo) & EqualityFormula(_y, _x))
        )
        self.assertEqual(
            ExistsFormula(_y, TripleFormula(_JohnDoe, _schema_name, _y)),
            ExistsFormula(_x, ExistsFormula(_y, TripleFormula(_x, _schema_name, _y)) & EqualityFormula(_x, _JohnDoe))
        )

        self.assertEqual(false_formula, ExistsFormula(_x, EqualityFormula(_x, _foo) & EqualityFormula(_x, _false)))

    def testTripleFormula(self):
        with self.assertRaises(ValueError):
            TripleFormula(_0, _schema_name, _foo)
        with self.assertRaises(ValueError):
            TripleFormula(_JohnDoe, _1, _foo)

    def testFunction(self):
        self.assertEqual(
            Function(_x, TripleFormula(_x, _schema_name, _foo)),
            Function(_y, TripleFormula(_y, _schema_name, _foo))
        )
        self.assertEqual(Function(_x, TripleFormula(_x, _schema_name, _foo)),
                         Function(_y, TripleFormula(_y, _schema_name, _foo)))

        self.assertEqual(Type.top(), Function(_x, true_formula).argument_type)
        self.assertEqual(Type.from_entity(xsd_boolean),
                         Function(_x, ExistsFormula(_y, EqualityFormula(_false, _x))).argument_type)
        self.assertEqual(
            Type.from_entity(xsd_string),
            Function(_x, EqualityFormula(_x, ValueFormula(XSDStringLiteral('foo')))).argument_type
        )
        self.assertEqual(
            Type.from_entity(xsd_string),
            Function(_x, EqualityFormula(_x, ValueFormula(XSDStringLiteral('foo')))).argument_type
        )
        self.assertEqual(
            Type.from_entity(schema_Person),
            Function(_x, TripleFormula(_x, _schema_name, _foo)).argument_type
        )
        self.assertEqual(
            Type.from_entity(schema_Person),
            Function(_x, TripleFormula(_x, _schema_name, _foo) & TripleFormula(_x, _schema_name, _bar)).argument_type
        )
        self.assertEqual(
            Type.from_entity(rdf_Property) & Type.from_entity(owl_Thing),
            Function(_x, TripleFormula(_JohnDoe, _x, _1)).argument_type
        )
        self.assertEqual(
            Type.from_entity(xsd_string),
            Function(_x, ExistsFormula(_y, TripleFormula(_y, _schema_name, _x))).argument_type
        )
        self.assertEqual(
            Type.from_entity(platypus_calendar),
            Function(_x, LowerFormula(_x, _2016)).argument_type
        )
        self.assertEqual(
            Type.from_entity(platypus_numeric),
            Function(_x, LowerFormula(_x, _1)).argument_type
        )

        self.assertTrue(Function(_x, true_formula))
        self.assertFalse(Function(_x, false_formula))
