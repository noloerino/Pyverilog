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
        if parent is None:
            self._hash = hash(value)
            self._len = 1
        else:
            self._hash = hash((parent._hash, value))
            self._len = parent._len + 1

    def __eq__(self, other):
        if not isinstance(other, _ScopeTreeNode) or self._len != other._len or self._hash != other._hash:
            return False
        if id(self) == id(other):
            return True
        p1 = self.parent
        p2 = other.parent
        if p1 is None and p2 is None:
            return self.value == other.value
        return self.value == other.value and p1 == p2

    def __hash__(self):
        return self._hash

class _ScopeTree:
    """
    Wraps a tree induced by _ScopeChainNodes.

    `curr` represents the "leaf" node representing the current outermost scope.
    `root` MUST be within the tree induced by `curr`, and represents the topmost
    node (inclusive) that this scope represents. This allows us to efficiently
    represent a slice of a ScopeChain.
    """

    def __init__(self, scopetree=None):
        if scopetree is None:
            self.root = None
            self.curr = None
            self._len = 0
        else:
            self.root = scopetree.root
            self.curr = scopetree.curr
            self._len = scopetree._len

    def __len__(self):
        return self._len

    def __iter__(self):
        # Unfortunately, the parent-facing nature of the tree pointers means we can't
        # lazily produce an iterator
        nodes = []
        node = self.curr
        while id(node) != id(self.root):
            nodes.append(node.value)
            node = node.parent
        if self.root is not None:
            nodes.append(self.root.value)
        return reversed(nodes)

    def __str__(self):
        return ".".join(repr(a) for a in self)

    def __eq__(self, other):
        if not isinstance(other, _ScopeTree):
            return False
        if self.root != other.root or self._len != other._len:
            return False
        return self.root == other.root and self.curr == other.curr

    def __hash__(self):
        return hash((self.root, self.curr))

    def __getitem__(self, key):
        if isinstance(key, slice):
            indices = key.indices(len(self))
            if len(indices) != 3:
                raise KeyError(indices)
            low, high, step = indices
            if step != 1:
                raise KeyError("_ScopeTree can only be indexed with slices with step 1")
            if high == low:
                return ScopeChain()
            new_curr = self.curr
            # High index is not inclusive
            # If the slice ends on index 2 and the tree has length 3, we need to go up
            # exactly 3 - 2 levels to reach index 1
            for _ in range(self._len - high):
                if new_curr is None or id(new_curr) == id(self.root):
                    raise IndexError(indices)
                new_curr = new_curr.parent
            new_root = new_curr
            # Low index is inclusive
            # If the slice goes from [0:2], new_curr would have ended on element 1, so
            # we need to do 2 - 0 - 1 iterations to get to the new root
            for _ in range(high - low - 1):
                if new_root is None or id(new_root) == id(self.root):
                    raise IndexError(indices)
                new_root = new_root.parent
            new_tree = _ScopeTree()
            new_tree.curr = new_curr
            new_tree.root = new_root
            new_tree._len = high - low
            new_scopechain = ScopeChain()
            new_scopechain.scopetree = new_tree
            return new_scopechain
        elif isinstance(key, int):
            if key < -self._len or key >= self._len:
                raise IndexError(key)
            if key < 0:
                # e.g. if we're length 4 and we need to access index -1, that's index 3
                key = self._len + key
            # calculate when to stop iterating through the tree
            # example: if curr is length 3 and we want to access index 2, we're already done
            # because index 2 is the current node (3 - 2 - 1 = 0)
            # if curr is length 3 and we want to access index 1, we need to go up
            # 3 - 1 - 1 = 1 levels in the tree
            node = self.curr
            for _ in range(self._len - key - 1):
                if node is None or id(node) == id(self.root):
                    raise IndexError(key)
                node = node.parent
            return node.value
        else:
            raise TypeError(key)


    def append(self, label: ScopeLabel):
        new_node = _ScopeTreeNode(label, self.curr)
        if self.curr is None:
            self.root = new_node
        self.curr = new_node
        self._len += 1

    def extend(self, scopechain: "ScopeChain"):
        for label in scopechain:
            self.append(label)

class ScopeChain(object):
    def __init__(self, scopechain=None):
        if scopechain is None:
            self.scopetree = _ScopeTree()
        elif isinstance(scopechain, ScopeChain):
            self.scopetree = _ScopeTree(scopechain.scopetree)
        elif isinstance(scopechain, list):
            self.scopetree = _ScopeTree()
            if len(scopechain) > 0:
                for label in scopechain:
                    self.scopetree.append(label)
        else:
            raise TypeError("cannot initialize ScopeChain from", scopechain)

    def __add__(self, r):
        new_chain = ScopeChain(self)
        if isinstance(r, ScopeLabel):
            new_chain.scopetree.append(r)
        elif isinstance(r, ScopeChain):
            new_chain.scopetree.extend(r)
        else:
            raise verror.DefinitionError('Can not add %s' % str(r))
        return new_chain

    def tocode(self):
        ret = []
        it = None
        for scope in self.scopetree:
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
        return [scope for scope in self.scopetree if scope.scopetype == 'module']

    def __repr__(self):
        ret = ''
        for scope in self.scopetree:
            l = scope.__repr__()
            ret += l + '.'
        ret = ret[:-1]
        return ret

    def __len__(self):
        return len(self.scopetree)

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self.scopetree == other.scopetree

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.scopetree)

    def __getitem__(self, key):
        return self.scopetree[key]

    def __iter__(self):
        return iter(self.scopetree)
