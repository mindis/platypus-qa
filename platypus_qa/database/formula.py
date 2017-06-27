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

import logging
from copy import copy
from functools import reduce
from itertools import chain, product
from typing import Union, List, Iterable, FrozenSet, Generic, TypeVar, Optional, Callable, Any

from platypus_qa.database.owl import Literal, Property, Class, Datatype, Entity, owl_Thing, rdfs_Literal, owl_Nothing, \
    XSDBooleanLiteral, xsd_boolean, rdf_Property, platypus_calendar, xsd_duration, platypus_numeric

"""
This file declares the Platypus intermediate format.

If it is composed of Formula and Function, both of them being Term.

Formulas are inspired by predicate logic and defined inductively with the two basic elements:
- ValueFormula being a wrapper for an RDF Term like http://schema.org/Person or "true"^^xsd:boolean
- VariableFormula being a variable.
and the constructors:
- AddFormula, SubFormula, MulFormula, DivFormula for the usual +, -, *, / binary arithmetic operator.
- OrFormula, AndFormula and NotFomula for the usual v, ∧ and ¬ logic operators.
(OrFormula and AndFormula may have an arbitrary number of operators).
- EqualityFormula for the equality comparison.
- GreaterFormula, GreaterOrEqualFormula, LowerFormula, LowerFormula for the usual >, ≥, < and ≤ comparison operators.
- ExistsFormula for variable introduction using the ∃ quantifier.
- TripleFormula for encoding RDF triples.
We define also overloading for the &, |, ~, <, <=, >=, >, +, -, *, / operators in order to ease the creation of formulas

Function[T] are defined as λ x . t where x is the function argument and t of type T is the body of the function.
Functions overrides the call operators (that does what it is supposed to do).

Various simplifications are implemented e.g. `(s, p, o) ∧ "true"^^xsd:boolean` is automaticaly transformed in `(s, p, o)`.


We also add typing to the formula.

Types are encoded with the Type class that may be constructed with the Type.top(), Type.bottom(), Type.from_entity
constructors.
To do types union or intersection use the | and & operators. The ordering operators are built in order to allows
inclusion comparison.
The top type is owl:Thing ⋃ rdfs:Literal and the bottom type is owl:Nothing.
The typing system assumes that the intersection of two datatypes that have no inclusion relation between them is always
empty.

We define then on Formula a type for the valuation (.type property) that is for the ValueFormula the type of its content,
Variable formula type.top(), xsd:boolean for boolean, triple, exists and comparison operators, and a relevant return
type for arithmetic operators (according to the operators, we consider that currently these operators are defined on
arithmetic and calendar XSD datatypes and xsd:duration).

We have also the Function.argument_type method, that returns an upper bound of the possible types of the argument that
makes the inner term relevant (e.g. a well defined truthy term).

TODO: Typing does not supports classes and properties.
"""


class Type:
    """
    Type for terms.
    To construct a type from a RDF Class or Datatype use Type.from_entity
    Use classical comparision operators (<,<=,>,>=,=,!=) to compare Types (using inclusion relationship)
    """
    _top = {}
    _bottom = None

    @staticmethod
    def from_entity(entity: Union[Class, Datatype]) -> 'Type':
        if isinstance(entity, Class):
            return _AtomicType(((entity,),))
        elif isinstance(entity, Datatype):
            return _AtomicType((), ((entity,),))
        else:
            raise ValueError('Parameter of Type.from_entity should be a Class or a Datatype')

    @staticmethod
    def tuple(*types: 'Type') -> 'Type':
        # we trim the end
        while len(types) and types[len(types) - 1] == Type.bottom():
            types = types[:-1]

        if len(types) == 0:
            return Type.bottom()
        elif len(types) == 1:
            return types[0]
        else:
            return _TupleType(*types)

    @classmethod
    def top(cls, arity: int = 1) -> 'Type':
        if arity not in cls._top:
            cls._top[arity] = Type.tuple(*(_AtomicType(((),), ((),)) for i in range(arity)))
        return cls._top[arity]

    @classmethod
    def bottom(cls) -> 'Type':
        if cls._bottom is None:
            cls._bottom = _AtomicType((), ())
        return cls._bottom

    def __getitem__(self, key: int) -> 'Type':
        raise NotImplementedError('Type.__getitem__ is not implemented')

    def __len__(self):
        raise NotImplementedError('Type.__len__ is not implemented')

    def __or__(self, other: 'Type'):
        raise NotImplementedError('Type.__or__ is not implemented')

    def __and__(self, other: 'Type'):
        raise NotImplementedError('Type.__and__ is not implemented')

    def __eq__(self, other):
        raise NotImplementedError('Type.__eq__ is not implemented')

    def __ne__(self, other):
        raise NotImplementedError('Type.__ne__ is not implemented')

    def __le__(self, other):
        raise NotImplementedError('Type.__le__ is not implemented')

    def __lt__(self, other):
        raise NotImplementedError('Type.__lt__ is not implemented')

    def __ge__(self, other):
        raise NotImplementedError('Type.__ge__ is not implemented')

    def __gt__(self, other):
        raise NotImplementedError('Type.__gt__ is not implemented')

    def __str__(self):
        raise NotImplementedError('Type.__str__ is not implemented')

    def __hash__(self) -> int:
        raise NotImplementedError('Type.__hash__ is not implemented')


class _TupleType(Type):
    def __init__(self, *types: Type):
        """
        Do not call directly but only Type.tuples in order to do normalization
        """
        self.types = types

    def __getitem__(self, key: int) -> Type:
        if key < len(self.types):
            return self.types[key]
        else:
            return Type.bottom()

    def __len__(self):
        return len(self.types)

    def __or__(self, other: Type) -> Type:
        return _TupleType(*(self[i].__or__(other[i]) for i in range(max(len(self), len(other)))))

    def __and__(self, other: Type) -> Type:
        return _TupleType(*(self[i].__and__(other[i]) for i in range(max(len(self), len(other)))))

    def __eq__(self, other):
        other = self._to_type(other)
        return isinstance(other, _TupleType) and self.types == other.types

    def __ne__(self, other):
        return not (self == other)

    def __le__(self, other):
        other = self._to_type(other)
        return all(self[i].__le__(other[i]) for i in range(max(len(self), len(other))))

    def __lt__(self, other):
        other = self._to_type(other)
        return all(self[i].__lt__(other[i]) for i in range(max(len(self), len(other))))

    def __ge__(self, other):
        other = self._to_type(other)
        return all(self[i].__ge__(other[i]) for i in range(max(len(self), len(other))))

    def __gt__(self, other):
        other = self._to_type(other)
        return all(self[i].__gt__(other[i]) for i in range(max(len(self), len(other))))

    @staticmethod
    def _to_type(other):
        if isinstance(other, Type):
            return other
        elif isinstance(other, (Class, Datatype)):
            return Type.from_entity(other)
        else:
            raise ValueError('{} is not a type'.format(other))

    def __str__(self):
        return '({})'.format(', '.join(str(t) for t in self.types))

    def __hash__(self) -> int:
        return hash(self.types)


class _AtomicType(Type):
    """
    Type without arity
    """
    _set_owl_Nothing = frozenset((owl_Nothing,))
    _set_owl_Thing = frozenset((owl_Thing,))
    _set_rdfs_Literal = frozenset((rdfs_Literal,))

    def __init__(self, entity: Iterable[Iterable[Class]] = (), literal: Iterable[Iterable[Datatype]] = ()):
        """
        Private constructor, use static factory methods
        """
        self._entity = self._simplify_class(entity)
        self._literal = self._simplify_datatype(literal)

    @staticmethod
    def _simplify_class(union: Iterable[Iterable[Class]]) -> FrozenSet[FrozenSet[Class]]:
        present = set(_AtomicType._simplify_class_intersection(inter) for inter in union)
        result = frozenset(inter for inter in present
                           if inter != _AtomicType._set_owl_Nothing and
                           not any(_AtomicType._class_intersection_is_in(inter, inter2) and inter != inter2
                                   for inter2 in present))
        return result if result else frozenset((_AtomicType._set_owl_Nothing,))

    @staticmethod
    def _simplify_datatype(union: Iterable[Iterable[Datatype]]) -> FrozenSet[FrozenSet[Datatype]]:
        present = set(
            inter for inter in (_AtomicType._simplify_datatype_intersection(inter) for inter in union) if
            inter is not None)
        return frozenset(inter for inter in present
                         if inter is not None and
                         not any(_AtomicType._datatype_intersection_is_in(inter, inter2) and inter != inter2
                                 for inter2 in present))

    @staticmethod
    def _class_intersection_is_in(sub: FrozenSet[Class], sup: FrozenSet[Class]) -> bool:
        return all(any(sub_elem.is_subclass_of(sup_elem) for sup_elem in sup) for sub_elem in sub)

    @staticmethod
    def _datatype_intersection_is_in(sub: FrozenSet[Datatype], sup: FrozenSet[Datatype]) -> bool:
        return all(any(sub_elem.is_restriction_of(sup_elem) for sup_elem in sup) for sub_elem in sub)

    @staticmethod
    def _simplify_class_intersection(intersection: Iterable[Class]) -> FrozenSet[Class]:
        present = set(intersection)
        result = frozenset(class_ for class_ in present
                           if not any(class_2.is_subclass_of(class_) and class_ != class_2 for class_2 in present))
        return result if len(result) else _AtomicType._set_owl_Thing

    @staticmethod
    def _simplify_datatype_intersection(intersection: Iterable[Datatype]) -> Optional[FrozenSet[Datatype]]:
        present = set(intersection)
        result = frozenset(dt for dt in present
                           if not any(dt2.is_restriction_of(dt) and dt != dt2 for dt2 in present))
        if len(result) == 0:
            return _AtomicType._set_rdfs_Literal
        # Intersection of two different datatypes D_1 and D_2 is empty if there is no restriction relation between them.
        return result if len(result) == 1 else None

    def __getitem__(self, key: int) -> 'Type':
        return self if key == 0 else Type.bottom()

    def __len__(self):
        return 1

    def __or__(self, other: Type) -> Type:
        if isinstance(other, _AtomicType):
            return _AtomicType(chain(self._entity, other._entity), chain(self._literal, other._literal))
        else:
            return other.__or__(self)

    def __and__(self, other: Type) -> Type:
        if isinstance(other, _AtomicType):
            return _AtomicType(
                [chain(*t) for t in product(self._entity, other._entity)],
                [chain(*t) for t in product(self._literal, other._literal)]
            )
        else:
            return other.__and__(self)

    def __eq__(self, other):
        other = self._to_type(other)
        if isinstance(other, _AtomicType):
            return self._entity == other._entity and self._literal == other._literal
        return False

    def __ne__(self, other):
        return not (self == other)

    def __le__(self, other):
        other = self._to_type(other)
        return (self | other) == other

    def __lt__(self, other):
        return self != other and self <= other

    def __ge__(self, other):
        return (self | self._to_type(other)) == self

    def __gt__(self, other):
        return self != other and self >= other

    @staticmethod
    def _to_type(other):
        if isinstance(other, Type):
            return other
        elif isinstance(other, (Class, Datatype)):
            return Type.from_entity(other)
        else:
            raise ValueError('{} is not a type'.format(other))

    def __str__(self):
        return ' ∪ '.join(chain(
            (' ∩ '.join(str(elem) for elem in inter) for inter in self._entity),
            (' ∩ '.join(str(elem) for elem in inter) for inter in self._literal)
        ))

    def __hash__(self) -> int:
        return hash(self._entity) ^ hash(self._literal)


_literal_type = Type.from_entity(rdfs_Literal)
_property_type = Type.from_entity(rdf_Property)
_boolean_type = Type.from_entity(xsd_boolean)
_numeric_type = Type.from_entity(platypus_numeric)
_calendar_type = Type.from_entity(platypus_calendar)
_duration_type = Type.from_entity(xsd_duration)


class _TypeForVariables(dict):
    def __missing__(self, key: 'VariableFormula') -> Type:
        return Type.top()

    def __delitem__(self, key: 'VariableFormula'):
        if key in self:
            super().__delitem__(key)

    def __and__(self, other: '_TypeForVariables'):
        result = copy(self)
        for variable, type_ in other.items():
            result[variable] &= type_
        return result

    def __or__(self, other: '_TypeForVariables'):
        result = copy(self)
        for variable, type_ in other.items():
            result[variable] |= type_
        return result

    def __str__(self):
        return '\n'.join('T({}) = {}'.format(k, v) for k, v in self.items())


class Term:
    @property
    def type(self) -> Type:
        raise NotImplementedError('Term.type is not implemented')

    @property
    def score(self) -> int:
        raise NotImplementedError('Term.score is not implemented')

    @property
    def original_str(self) -> Optional[str]:
        return None

    def substitute(self, var: 'VariableFormula', formula: 'Formula') -> 'Term':
        """
        Substitutes var by term in the expression
        """
        raise NotImplementedError('Term.substitute is not implemented')

    def _variables_types(self) -> _TypeForVariables:
        """
        Returns a type for each free variable
        """
        return _TypeForVariables()

    def explore(self, function: Callable[['Term'], Any]):
        function(self)

    def __str__(self) -> str:
        raise ValueError('Term.__str__ is not implemented')

    def __eq__(self, other) -> bool:
        raise ValueError('Term.__eq__ is not implemented')

    def __hash__(self) -> int:
        raise ValueError('Term.__hash__ is not implemented')

    def __bool__(self) -> bool:
        raise ValueError('Term.__bool__ is not implemented')

    def __getitem__(self, key) -> 'Term':
        """
        Get an element in the tuple
        """
        raise NotImplementedError('Term.__getitem__ is not implemented')

    def __len__(self):
        raise NotImplementedError('Term.__len__ is not implemented')


class Formula(Term):
    def __bool__(self) -> bool:
        return True  # Currently the only false formula is the formula "⊥"

    def __and__(self, other: 'Formula') -> 'Formula':
        return AndFormula([self, other])

    def __or__(self, other: 'Formula') -> 'Formula':
        return OrFormula([self, other])

    def __invert__(self) -> 'Formula':
        return NotFormula(self)

    def __add__(self, other: 'Formula') -> 'Formula':
        return AddFormula(self, other)

    def __sub__(self, other: 'Formula') -> 'Formula':
        return SubFormula(self, other)

    def __mul__(self, other: 'Formula') -> 'Formula':
        return MulFormula(self, other)

    def __truediv__(self, other: 'Formula') -> 'Formula':
        return DivFormula(self, other)

    def __gt__(self, other: 'Formula') -> 'Formula':
        return GreaterFormula(self, other)

    def __ge__(self, other: 'Formula') -> 'Formula':
        return GreaterOrEqualFormula(self, other)

    def __lt__(self, other: 'Formula') -> 'Formula':
        return LowerFormula(self, other)

    def __le__(self, other: 'Formula') -> 'Formula':
        return LowerOrEqualFormula(self, other)

    def __getitem__(self, key: int) -> Term:
        if key != 0:
            raise IndexError('Formula has only one member')
        return self

    def __len__(self):
        return 1


class VariableFormula(Formula):
    def __init__(self, name: str):
        self.name = name

    def substitute(self, var: 'VariableFormula', formula: Formula) -> Formula:
        if self == var:
            return formula
        else:
            return self

    @property
    def type(self) -> Type:
        return Type.top()

    @property
    def score(self) -> int:
        return 0

    def __str__(self) -> str:
        return '?{}'.format(self.name)

    def __eq__(self, other) -> bool:
        return isinstance(other, VariableFormula) and self.name == other.name

    def __hash__(self) -> int:
        return 2  # constant because of alpha-conversion


class ValueFormula(Formula):
    def __init__(self, term: Union[Entity, Literal], original_str: Optional[str] = None):
        self.term = term
        self._original_str = original_str

    def substitute(self, var: VariableFormula, formula: Formula) -> 'ValueFormula':
        return self

    @property
    def type(self) -> Type:
        if isinstance(self.term, Entity):
            return reduce(lambda a, b: a | b, (Type.from_entity(type_) for type_ in self.term.types))
        elif isinstance(self.term, Literal):
            return Type.from_entity(self.term.datatype)
        else:
            raise ValueError('Unexpected term in ValueFormula: {}'.format(self.term))

    @property
    def score(self) -> int:
        if isinstance(self.term, Entity):
            return self.term.score
        else:
            return 1

    @property
    def original_str(self) -> Optional[str]:
        return self._original_str

    def __bool__(self) -> bool:
        return self != false_formula  # TODO: what about 0^^xsd:interger?

    def __str__(self) -> str:
        return str(self.term)

    def __eq__(self, other) -> bool:
        return isinstance(other, ValueFormula) and self.term == other.term

    def __hash__(self) -> int:
        return hash(self.term)


true_formula = ValueFormula(XSDBooleanLiteral(True))
false_formula = ValueFormula(XSDBooleanLiteral(False))


class BinaryArithmeticOperatorFormula(Formula):
    def __init__(self, left: Formula, right: Formula):
        if left.type & _numeric_type == Type.bottom():
            raise ValueError('Arithmetic operators expects numeric left operand')
        if right.type & _numeric_type == Type.bottom():
            raise ValueError('Arithmetic operators expects numeric right operand')
        self.left = left
        self.right = right

    def substitute(self, var: VariableFormula, formula: Formula) -> Formula:
        return type(self)(
            self.left.substitute(var, formula),
            self.right.substitute(var, formula)
        )

    def _variables_types(self) -> _TypeForVariables:
        # TODO: What if we uses these operators on other things than arithmetic values?
        result = self.left._variables_types() & self.right._variables_types()
        if isinstance(self.left, VariableFormula):
            result[self.left] &= _numeric_type
        elif isinstance(self.right, VariableFormula):
            result[self.right] &= _numeric_type
        return result

    @property
    def type(self) -> Type:
        return _numeric_type

    @property
    def score(self) -> int:
        return max(self.left.score, self.right.score)

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        self.left.explore(function)
        self.right.explore(function)

    def __eq__(self, other) -> bool:
        return isinstance(other, type(self)) and self.left == other.left and self.right == other.right

    def __hash__(self) -> int:
        return hash(self.left) ^ hash(self.right)


class SymmetricArithmeticBinaryOperatorFormula(BinaryArithmeticOperatorFormula):
    def __eq__(self, other) -> bool:
        return isinstance(other, type(self)) and (self.left == other.left and self.right == other.right or
                                                  self.left == other.right and self.right == other.left)

    def __hash__(self) -> int:
        return hash(self.left) ^ hash(self.right)


class AddFormula(SymmetricArithmeticBinaryOperatorFormula):
    def __str__(self):
        return '({} + {})'.format(self.left, self.right)


class SubFormula(BinaryArithmeticOperatorFormula):
    def __str__(self):
        return '({} - {})'.format(self.left, self.right)


class MulFormula(SymmetricArithmeticBinaryOperatorFormula):
    def __str__(self):
        return '({} * {})'.format(self.left, self.right)


class DivFormula(BinaryArithmeticOperatorFormula):
    def __str__(self):
        return '({} / {})'.format(self.left, self.right)


class AndFormula(Formula):
    def __new__(cls, args: List[Formula]):
        # Moves to disjunctive normal form and filters True and False
        clauses = [[]]
        for arg in args:
            if arg == true_formula:
                continue
            elif arg == false_formula:
                return arg
            elif isinstance(arg, OrFormula):
                clauses = [clause + [arg2] for clause in clauses for arg2 in arg.args]
            else:
                for clause in clauses:
                    clause.append(arg)
        if len(clauses) > 1:
            return OrFormula([AndFormula(clause) for clause in clauses])

        if len(clauses[0]) == 0:
            return true_formula
        elif len(clauses[0]) == 1:
            return clauses[0][0]
        else:
            return super(AndFormula, cls).__new__(cls)

    def __init__(self, args: List[Formula]):
        # Flattening
        filtered_arguments = []
        for argument in args:
            if isinstance(argument, AndFormula):
                filtered_arguments.extend(argument.args)
            elif argument == true_formula:
                continue
            else:
                filtered_arguments.append(argument)

        self.args = frozenset(filtered_arguments)

    def substitute(self, var: VariableFormula, formula: Formula) -> Formula:
        return AndFormula([arg.substitute(var, formula) for arg in self.args])

    @property
    def type(self) -> Type:
        return _boolean_type

    @property
    def score(self) -> int:
        return max(arg.score for arg in self.args)

    def _variables_types(self) -> _TypeForVariables:
        return reduce(lambda a, b: a & b, (arg._variables_types() for arg in self.args))

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        for arg in self.args:
            arg.explore(function)

    def __str__(self):
        return '({})'.format(' ∧ '.join(str(arg) for arg in self.args))

    def __eq__(self, other) -> bool:
        return isinstance(other, AndFormula) and self.args == other.args

    def __hash__(self) -> int:
        return hash(self.args) * 8


class OrFormula(Formula):
    def __new__(cls, args: List[Formula]):
        # Lookup True and False
        filtered_arguments = []
        for argument in args:
            if argument == false_formula:
                continue
            elif argument == true_formula:
                return argument
            else:
                filtered_arguments.append(argument)

        if len(filtered_arguments) == 0:
            return false_formula
        elif len(filtered_arguments) == 1:
            return filtered_arguments[0]
        else:
            return super(OrFormula, cls).__new__(cls)

    def __init__(self, args: List[Formula]):
        # Flattening
        filtered_arguments = []
        for argument in args:
            if isinstance(argument, OrFormula):
                filtered_arguments.extend(argument.args)
            elif argument == false_formula:
                continue
            else:
                filtered_arguments.append(argument)

        self.args = frozenset(filtered_arguments)

    def substitute(self, var: VariableFormula, formula: Formula) -> Formula:
        return OrFormula([arg.substitute(var, formula) for arg in self.args])

    @property
    def type(self) -> Type:
        return _boolean_type

    @property
    def score(self) -> int:
        return max(arg.score for arg in self.args)

    def _variables_types(self) -> _TypeForVariables:
        return reduce(lambda a, b: a | b, (arg._variables_types() for arg in self.args))

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        for arg in self.args:
            arg.explore(function)

    def __str__(self):
        return '({})'.format(' ∨ '.join(str(arg) for arg in self.args))

    def __eq__(self, other) -> bool:
        return isinstance(other, OrFormula) and self.args == other.args

    def __hash__(self) -> int:
        return hash(self.args) * 8 + 3


class NotFormula(Formula):
    def __new__(cls, arg: Formula):
        if arg == true_formula:
            return false_formula
        elif arg == false_formula:
            return true_formula
        elif isinstance(arg, NotFormula):
            return arg.arg
        elif isinstance(arg, AndFormula):
            return OrFormula([NotFormula(arg) for arg in arg.args])
        elif isinstance(arg, OrFormula):
            return AndFormula([NotFormula(arg) for arg in arg.args])
        else:
            return super(NotFormula, cls).__new__(cls)

    def __init__(self, arg: Formula):
        self.arg = arg

    def substitute(self, var: VariableFormula, formula: Formula) -> Formula:
        return NotFormula(self.arg.substitute(var, formula))

    @property
    def type(self) -> Type:
        return _boolean_type

    @property
    def score(self) -> int:
        return self.arg.score

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        self.arg.explore(function)

    def __str__(self):
        return '¬ {}'.format(str(self.arg))

    def __eq__(self, other) -> bool:
        return isinstance(other, NotFormula) and self.arg == other.arg

    def __hash__(self) -> int:
        return - hash(self.arg)


class EqualityFormula(Formula):
    def __new__(cls, left: Formula, right: Formula):
        if left == right:
            return true_formula
        elif isinstance(left, ValueFormula) and isinstance(right, ValueFormula):
            return false_formula  # left != right
            # TODO: handle owl:sameAs and this kind of constructs?
        else:
            return super(EqualityFormula, cls).__new__(cls)

    def __init__(self, left: Formula, right: Formula):
        self.left = left
        self.right = right

    def substitute(self, var: VariableFormula, formula: Formula) -> Formula:
        return EqualityFormula(self.left.substitute(var, formula), self.right.substitute(var, formula))

    @property
    def type(self) -> Type:
        return Type.from_entity(xsd_boolean)

    @property
    def score(self) -> int:
        return max(self.left.score, self.right.score)

    def _variables_types(self) -> _TypeForVariables:
        result = self.left._variables_types() & self.right._variables_types()
        if isinstance(self.left, VariableFormula):
            result[self.left] &= self.right.type
        if isinstance(self.right, VariableFormula):
            result[self.right] &= self.left.type
        return result  # TODO: do unification if both operands are variables?

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        self.left.explore(function)
        self.right.explore(function)

    def __str__(self):
        return '[{} = {}]'.format(self.left, self.right)

    def __eq__(self, other) -> bool:
        return isinstance(other, EqualityFormula) and (
            (self.left == other.left and self.right == other.right) or
            (self.left == other.right and self.right == other.left))

    def __hash__(self) -> int:
        return hash(self.left) ^ hash(self.right)


class BinaryOrderOperatorFormula(Formula):
    def __init__(self, left: Formula, right: Formula):
        if self._get_type_for_ordering(left) == Type.bottom():
            raise ValueError('Order operators expects an orderable left operand')
        if self._get_type_for_ordering(right) == Type.bottom():
            raise ValueError('Order operators expects and orderable right operand')
        self.left = left
        self.right = right

    def substitute(self, var: VariableFormula, formula: Formula) -> Formula:
        return type(self)(
            self.left.substitute(var, formula),
            self.right.substitute(var, formula)
        )

    def _variables_types(self) -> _TypeForVariables:
        # Only literals has an order and they should be compatible (i.e. has the same broad type)
        result = self.left._variables_types() & self.right._variables_types()
        operand_type = self._get_type_for_ordering(self.left) & self._get_type_for_ordering(self.right)
        if isinstance(self.left, VariableFormula):
            result[self.left] &= operand_type
        if isinstance(self.right, VariableFormula):
            result[self.right] &= operand_type
        return result

    @staticmethod
    def _get_type_for_ordering(formula: Formula):
        result_type = Type.bottom()
        if formula.type & _numeric_type != Type.bottom():
            result_type |= _numeric_type
        if formula.type & _calendar_type != Type.bottom():
            result_type |= _calendar_type
        if formula.type & _duration_type != Type.bottom():
            result_type |= _duration_type
        return result_type

    @property
    def type(self) -> Type:
        return _boolean_type

    @property
    def score(self) -> int:
        return max(self.left.score, self.right.score)

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        self.left.explore(function)
        self.right.explore(function)

    def __eq__(self, other) -> bool:
        return isinstance(other, type(self)) and self.left == other.left and self.right == other.right

    def __hash__(self) -> int:
        return hash(self.left) ^ hash(self.right)


class GreaterFormula(BinaryOrderOperatorFormula):
    def __str__(self):
        return '[{} > {}]'.format(self.left, self.right)


class GreaterOrEqualFormula(BinaryOrderOperatorFormula):
    def __str__(self):
        return '[{} ≥ {}]'.format(self.left, self.right)


class LowerFormula(BinaryOrderOperatorFormula):
    def __str__(self):
        return '[{} < {}]'.format(self.left, self.right)


class LowerOrEqualFormula(BinaryOrderOperatorFormula):
    def __str__(self):
        return '[{} ≤ {}]'.format(self.left, self.right)


class ExistsFormula(Formula):
    def __new__(cls, argument: VariableFormula, body: Formula):
        if body == true_formula or body == false_formula:
            return body  # TODO: more general, if argument is not used in the body
        if isinstance(body, OrFormula):  # we distributes the exists on the or
            return OrFormula([ExistsFormula(argument, arg) for arg in body.args])

        # We try to find an hardcoded value for argument, if yes, the exists constraint is obviously true
        # and so we just have to check if the remaining parts of the formula are true
        elif isinstance(body, EqualityFormula):
            if body.left == argument:
                return body.substitute(argument, body.right)
            elif body.right == argument:
                return body.substitute(argument, body.left)
        elif isinstance(body, AndFormula):
            for child in body.args:
                if isinstance(child, EqualityFormula):
                    if child.left == argument:
                        return body.substitute(argument, child.right)
                    elif child.right == argument:
                        return body.substitute(argument, child.left)

        # We try to see if the type of argument is bottom, if yes, the formula is always False
        if body._variables_types()[argument] == Type.bottom():
            return false_formula

        return super(ExistsFormula, cls).__new__(cls)

    def __init__(self, argument: VariableFormula, body: Formula):
        if hasattr(self, 'argument'):
            return  # do not modified if already __init__
        self.argument = argument
        self.body = body

    def substitute(self, var: VariableFormula, formula: Formula) -> Formula:
        if var == self.argument:
            return self  # Variable shadowing
        return ExistsFormula(self.argument, self.body.substitute(var, formula))

    @property
    def type(self) -> Type:
        return _boolean_type

    @property
    def score(self) -> int:
        return self.body.score

    def _variables_types(self) -> _TypeForVariables:
        body_types = copy(self.body._variables_types())
        del body_types[self.argument]  # shadowing
        return body_types

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        self.body.explore(function)

    def __str__(self):
        return '∃ {} {}'.format(self.argument, self.body)

    def __eq__(self, other) -> bool:
        return isinstance(other, ExistsFormula) and self.body == other.body.substitute(other.argument, self.argument)

    def __hash__(self) -> int:
        return hash(self.body) * 8 + 5


class TripleFormula(Formula):
    def __init__(self, subject: Formula, predicate: Formula, _object: Formula):
        if subject.type <= _literal_type:
            raise ValueError('Triple subject should not be a literal')
        if predicate.type & _property_type == Type.bottom():
            raise ValueError('Triple predicate should be instance of rdf:Property')
        self.subject = subject
        self.predicate = predicate
        self.object = _object

    def substitute(self, var: VariableFormula, formula: Formula) -> Formula:
        return TripleFormula(self.subject.substitute(var, formula),
                             self.predicate.substitute(var, formula),
                             self.object.substitute(var, formula))

    @property
    def type(self) -> Type:
        return _boolean_type

    @property
    def score(self) -> int:
        return max(self.subject.score, self.object.score)

    def _variables_types(self) -> _TypeForVariables:
        result = _TypeForVariables()

        # structural types
        if isinstance(self.subject, VariableFormula):
            result[self.subject] &= Type.from_entity(owl_Thing)
        if isinstance(self.predicate, VariableFormula):
            result[self.predicate] &= Type.from_entity(rdf_Property)

        # domain and range
        if isinstance(self.predicate, ValueFormula):
            if isinstance(self.predicate.term, Property):
                if isinstance(self.subject, VariableFormula):
                    result[self.subject] &= Type.from_entity(self.predicate.term.domain)
                if isinstance(self.object, VariableFormula):
                    result[self.object] &= Type.from_entity(self.predicate.term.range)

        return result

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        self.subject.explore(function)
        self.predicate.explore(function)
        self.object.explore(function)

    def __str__(self):
        return '<{}, {}, {}>'.format(self.subject, self.predicate, self.object)

    def __eq__(self, other) -> bool:
        return isinstance(other, TripleFormula) and self.subject == other.subject and \
               self.predicate == other.predicate and self.object == other.object

    def __hash__(self) -> int:
        return hash(self.subject) ^ hash(self.predicate) ^ hash(self.object)


class Tuple(Term):
    def __new__(cls, *elements):
        if len(elements) == 1:
            return elements[0]
        else:
            return super(Tuple, cls).__new__(cls)

    def __init__(self, *elements):
        self._elements = elements

    @property
    def type(self) -> Type:
        return Type.tuple(*(e.type for e in self._elements))

    @property
    def score(self) -> int:
        return max(e.score for e in self._elements)

    def substitute(self, var: VariableFormula, formula: Formula) -> Term:
        return Tuple(*(e.substitute(var, formula) for e in self._elements))

    def _variables_types(self) -> _TypeForVariables:
        return reduce(lambda a, b: a | b, (e._variables_types() for e in self._elements))

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        for e in self._elements:
            e.explore(function)

    def __str__(self) -> str:
        return '({})'.format(', '.join(str(e) for e in self._elements))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Tuple):
            return False
        return self._elements == other._elements

    def __hash__(self) -> int:
        return hash(self._elements)

    def __bool__(self) -> bool:
        return all(bool(e) for e in self._elements)

    def __getitem__(self, key: int) -> Term:
        return self._elements[key]

    def __len__(self):
        return len(self._elements)


T = TypeVar('T')


class Select(Term, Generic[T]):
    def __init__(self, args: Union[VariableFormula, Iterable[VariableFormula]], body: Formula):
        if isinstance(args, VariableFormula):
            self.args = args,
        else:
            self.args = tuple(args)
        if isinstance(body, Select):
            logging.getLogger('formula').warning('Nested select is deprecated', DeprecationWarning)
            self.args += body.args
            body = body.body
        self.body = body

    def substitute(self, var: VariableFormula, formula: Formula) -> 'Select':
        if var in self.args:
            return self  # Variable shadowing
        return Select(self.args, self.body.substitute(var, formula))

    @property
    def score(self) -> int:
        return self.body.score

    def _variables_types(self) -> _TypeForVariables:
        body_types = copy(self.body._variables_types())
        for arg in self.args:
            del body_types[arg]  # shadowing
        return body_types

    def explore(self, function: Callable[[Term], Any]):
        function(self)
        self.body.explore(function)

    @property
    def type(self) -> Type:
        body_types = self.body._variables_types()
        return Type.tuple(*(body_types[arg] for arg in self.args))

    def bind(self, key: int, value: Term) -> 'Union[Formula,Select]':
        """
        Binds the first variable
        """
        if len(self.args) == 1:
            return self.body.substitute(self.args[0], value)
        else:
            return Select(self.args[1:], self.body.substitute(self.args[0], value))

    def __call__(self, value: Term) -> 'Union[Formula,Select]':
        """
        Binds the first variable
        """
        return self.bind(0, value)

    def __str__(self):
        return '{' + ' {} | {} '.format(', '.join(str(arg) for arg in self.args), self.body) + '}'

    def __bool__(self) -> bool:
        return bool(self.body)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Select):
            return False
        if len(self.args) != len(other.args):
            return False
        normalize_body = other.body
        for i in range(len(self.args)):
            normalize_body = normalize_body.substitute(other.args[i], self.args[i])
        return isinstance(other, Select) and self.body == normalize_body

    def __len__(self):
        return len(self.args)

    def __getitem__(self, key: int) -> Term:
        """
        Does projection on the key-iest variable. TODO: is it the right behaviour?
        """
        return Select([self.args[key]], self.body)

    def __hash__(self) -> int:
        return hash(self.body) * 8 + 4

    def swap_arguments(self, key1: int = 0, key2: int = 1) -> 'Select':
        args = list(self.args)
        args[key1], args[key2] = args[key2], args[key1]
        return Select(args, self.body)
