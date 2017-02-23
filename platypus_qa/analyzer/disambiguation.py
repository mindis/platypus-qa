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
from collections import defaultdict, Iterable
from typing import List, Dict, Union

from platypus_qa.database.formula import Term


class DisambiguationStep:
    def __init__(self, str_to_disambiguate: str, possibilities: Dict[Term, Union['DisambiguationStep', List[Term]]],
                 others: Union['DisambiguationStep', List[Term]]):
        self.str_to_disambiguate = str_to_disambiguate
        self.possibilities = possibilities
        self.others = others

    def __str__(self):
        return '({}: ({}))'.format(
            self.str_to_disambiguate,
            ', '.join('{}: {}'.format(k, self._str_with_list(v)) for k, v in self.possibilities.items()))

    @staticmethod
    def _str_with_list(value):
        if isinstance(value, Iterable):
            return '[{}]'.format(', '.join(str(f) for f in value))
        else:
            return str(value)


def find_process(full_terms: List[Term]) -> Union[DisambiguationStep, List[Term]]:
    """
    Returns a disambiguation process for a set of Term related to the same natural language sentence
    It returns a tree where is vertex is a Term related to an entity to disambiguate and each edge is a possible
    meaning.
    The current algorithm is probably not optimal. Finding an optimal solution (according to which critera?) seems
    to be a nice problem.
    """

    # Each full terms is associated with a map with for each language label the associated partial term
    all_full_terms_with_trace = []
    for full_term in full_terms:
        trace = {}

        def find_term_with_str(term: Term):
            if term.original_str is not None:
                trace[term.original_str] = term

        full_term.explore(find_term_with_str)
        all_full_terms_with_trace.append((full_term, trace))

    def build_tree(full_terms_with_trace):
        # Let's find the most discriminative string
        str_possible_terms = defaultdict(set)
        for _, trace in full_terms_with_trace:
            for key, value in trace.items():
                str_possible_terms[key].add(value)
        key_term_by_usage = sorted(str_possible_terms.items(), key=lambda t: len(t[1]), reverse=True)

        if not key_term_by_usage or len(key_term_by_usage[0][1]) < 2:
            return [term for term, trace in full_terms_with_trace]  # no discriminative term

        discriminative_str = key_term_by_usage[0][0]

        # We regroup full terms by chosen term for this str
        full_terms_with_trace_by_discriminative_str_term = defaultdict(list)
        others_full_terms_with_trace = []
        for full_term, trace in full_terms_with_trace:
            if discriminative_str in trace:
                new_trace = dict(trace)
                del new_trace[discriminative_str]
                full_terms_with_trace_by_discriminative_str_term[trace[discriminative_str]].append(
                    (full_term, new_trace))
            else:
                others_full_terms_with_trace.append((full_term, trace))  # TODO: bad

        return DisambiguationStep(discriminative_str,
                                  {k: build_tree(v) for k, v in
                                   full_terms_with_trace_by_discriminative_str_term.items()},
                                  build_tree(others_full_terms_with_trace))

    return build_tree(all_full_terms_with_trace)
