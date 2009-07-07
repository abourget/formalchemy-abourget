# Copyright (C) 2007 Alexandre Conrad, alexandre (dot) conrad (at) gmail (dot) com
# Copyright (C) 2009 Alexandre Bourget, alex@bourget.cc
#
# This module is part of FormAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

from formalchemy import config
from sqlalchemy.orm import Query, class_mapper
from sqlalchemy.exceptions import InvalidRequestError # 0.4 support
import compiler

__all__ = ['stringify', 'normalized_options', '_pk', '_pk_one_column',
           'simple_eval']

# see http://code.activestate.com/recipes/364469/ for explanation.
# 2.6 provides ast.literal_eval, but requiring 2.6 is a bit of a stretch for now
class _SafeEval(object):
    def visit(self, node,**kw):
        cls = node.__class__
        meth = getattr(self, 'visit' + cls.__name__, self.default)
        return meth(node, **kw)
            
    def default(self, node, **kw):
        for child in node.getChildNodes():
            return self.visit(child, **kw)
            
    visitExpression = default
    
    def visitName(self, node, **kw):
        if node.name in ['True', 'False', 'None']:
            return eval(node.name)

    def visitConst(self, node, **kw):
        return node.value

    def visitTuple(self,node, **kw):
        return tuple(self.visit(i) for i in node.nodes)
        
    def visitList(self,node, **kw):
        return [self.visit(i) for i in node.nodes]

def simple_eval(source):
    """like 2.6's ast.literal_eval, but only does constants, lists, and tuples, for serialized pk eval"""
    if source == '':
        return None
    walker = _SafeEval()
    ast = compiler.parse(source, 'eval')
    return walker.visit(ast)


def stringify(k, null_value=u''):
    if k is None:
        return null_value
    if isinstance(k, str):
        return unicode(k, config.encoding)
    elif isinstance(k, unicode):
        return k
    elif hasattr(k, '__unicode__'):
        return unicode(k)
    else:
        return unicode(str(k), config.encoding)

def _pk_one_column(instance, column):
    try:
        attr = getattr(instance, column.key)
    except AttributeError:
        # FIXME: this is not clean but the only way i've found to retrieve the
        # real attribute name of the primary key.
        # This is needed when you use something like:
        #    id = Column('UGLY_NAMED_ID', primary_key=True)
        # It's a *really* needed feature
        cls = instance.__class__
        for k in instance._sa_class_manager.keys():
            props = getattr(cls, k).property
            if hasattr(props, 'columns'):
                if props.columns[0] is column:
                    attr = getattr(instance, k)
                    break
    return attr

def _pk(instance):
    # Return the value of this instance's primary key, suitable for passing to Query.get().  
    # Will be a tuple if PK is multicolumn.
    try:
        columns = class_mapper(type(instance)).primary_key
    except InvalidRequestError:
        return None
    if len(columns) == 1:
        return _pk_one_column(instance, columns[0])
    return tuple([_pk_one_column(instance, column) for column in columns])



def query_options(L):
    """
    Return a list of tuples of `(item description, item pk)`
    for each item in the iterable L, where `item description`
    is the result of str(item) and `item pk` is the item's primary key.
    """
    return [(stringify(item), _pk(item)) for item in L]


def normalized_options(options):
    """
    If `options` is an SA query or an iterable of SA instances, it will be
    turned into a list of `(item description, item value)` pairs. Otherwise, a
    copy of the original options will be returned with no further validation.
    """
    if isinstance(options, Query):
        options = options.all()
    if callable(options):
        return options
    i = iter(options)
    try:
        first = i.next()
    except StopIteration:
        return []
    try:
        class_mapper(type(first))
    except:
        return list(options)
    return query_options(options)

