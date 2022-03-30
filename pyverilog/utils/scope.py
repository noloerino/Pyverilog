# -------------------------------------------------------------------------------
# scope.py
#
# classes for definition of scope
#
# Copyright (C) 2013, Shinya Takamaeda-Yamazaki
# License: Apache 2.0
# -------------------------------------------------------------------------------
from __future__ import absolute_import
from __future__ import print_function
import sys
import os

scopetype_list_unprint = ('generate', 'always', 'function',  # 'functioncall',
                          'task', 'taskcall', 'initial', 'for', 'while', 'if')
scopetype_list_print = ('module', 'block', 'signal', 'functioncall',)
scopetype_list = scopetype_list_unprint + scopetype_list_print + ('any', )


class ScopeLabel(object):
    def __init__(self, scopename, scopetype='any', scopeloop=None):
        self.scopename = scopename
        if scopetype not in scopetype_list:
            raise DefinitionError('No such Scope type')
        self.scopetype = scopetype
        self.scopeloop = scopeloop

    def __repr__(self):
        ret = []
        ret.append(self.scopename)
        if self.scopeloop is not None:
            ret.append('[')
            ret.append(str(self.scopeloop))
            ret.append(']')
        return ''.join(ret)

    def tocode(self):
        if self.scopetype in scopetype_list_unprint:
            return ''
        return self.scopename

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if self.scopetype == 'any' or other.scopetype == 'any':
            return ((self.scopename, self.scopeloop)
                    == (other.scopename, other.scopeloop))
        return (self.scopename, self.scopetype, self.scopeloop) == (other.scopename, other.scopetype, other.scopeloop)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        # return hash((self.scopename, self.scopetype, self.scopeloop))
        return hash((self.scopename, self.scopeloop))  # to use for dict key with any scopetype

    def isPrintable(self):
        return self.scopetype in (scopetype_list_print + ('any',))

class _ScopeTreeNode:
    """
    Represents a portion of a ScopeChain. This representation avoids the need to repeatedly
    make deep copies of ScopeChains, which can become expensive.

    For example, a ScopeChain representing the scope "top.sub.x" would be constructed by
    pseudocode of the form Node("x", Node("sub", Node("top")))
    """
    def __init__(self, value: ScopeLabel, parent=None):
        self.value = value
        self.parent = parent # Parent _ScopeTreeNode
        self._hash = None # memoized hash
        if parent is None:
            self._len = 1
        else:
            self._len = len(parent) + 1

    def __len__(self):
        return self._len

    def __iter__(self):
        # Unfortunately, the parent-facing nature of the tree pointers means we can't
        # lazily produce an iterator
        nodes = []
        node = self
        while node is not None:
            nodes.append(node.value)
            node = node.parent
        return reversed(nodes)

    def __eq__(self, other):
        if not isinstance(other, _ScopeTreeNode):
            return False
        if id(self) == id(other):
            return True
        p1 = self.parent
        p2 = other.parent
        if p1 is None and p2 is None:
            return self.value == other.value
        return self.value == other.value and p1 == p2

    def __hash__(self):
        if self._hash is not None:
            return self._hash
        self._hash = hash((self.parent, self.value))
        return self._hash

class ScopeChain(object):
    def __init__(self, scopechain=None):
        if scopechain is None:
            self.scopenode = None
        elif isinstance(scopechain, ScopeChain):
            self.scopenode = scopechain.scopenode
        elif isinstance(scopechain, list):
            if len(scopechain) == 0:
                self.scopenode = None
            else:
                first_label = scopechain[0]
                self.scopenode = _ScopeTreeNode(first_label, None)
                for label in scopechain[1:]:
                    self.scopenode = _ScopeTreeNode(label, self.scopenode)
        else:
            raise TypeError("cannot initialize ScopeChain from", scopechain)

    def __add__(self, r):
        new_chain = ScopeChain(self)
        if isinstance(r, ScopeLabel):
            new_chain.scopenode = _ScopeTreeNode(r, new_chain.scopenode)
        elif isinstance(r, ScopeChain):
            for label in r:
                new_chain.scopenode = _ScopeTreeNode(label, new_chain.scopenode)
        else:
            raise verror.DefinitionError('Can not add %s' % str(r))
        return new_chain

    def tocode(self):
        ret = []
        it = None
        if self.scopenode is None:
            return ret
        for scope in self.scopenode:
            l = scope.tocode()
            if l:
                ret.append(l)
            if it is not None:
                ret.append(it)
            if l:
                # ret.append('.')
                # ret.append('_dot_')
                ret.append('_')
            if scope.scopetype == 'for' and scope.scopeloop is not None:
                #it = '[' + str(scope.scopeloop) + ']'
                #it = '_L_' + str(scope.scopeloop) + '_R_'
                it = '_' + str(scope.scopeloop) + '_'
            else:
                it = None
        ret = ret[:-1]
        return ''.join(ret)

    def get_module_list(self):
        return [scope for scope in self.scopenode if scope.scopetype == 'module']

    def __repr__(self):
        ret = ''
        if self.scopenode is None:
            return ret
        for scope in self.scopenode:
            l = scope.__repr__()
            ret += l + '.'
        ret = ret[:-1]
        return ret

    def __len__(self):
        if self.scopenode is None:
            return 0
        return len(self.scopenode)

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self.scopenode == other.scopenode

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.scopenode)

    def __getitem__(self, key):
        # TODO this algorithm can be optimized
        scope_lst = list(iter(self.scopenode))
        if isinstance(key, slice):
            indices = key.indices(len(self))
            return ScopeChain([scope_lst[x] for x in range(*indices)])
        return scope_lst[key]

    def __iter__(self):
        if self.scopenode is None:
            return iter(tuple())
        return iter(self.scopenode)
