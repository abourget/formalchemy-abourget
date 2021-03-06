# Copyright (C) 2007 Alexandre Conrad, alexandre (dot) conrad (at) gmail (dot) com
#
# This module is part of FormAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

import cgi
import warnings
import logging
logger = logging.getLogger('formalchemy.' + __name__)

MIN_SA_VERSION = '0.4.5'
from sqlalchemy import __version__
if __version__.split('.') < MIN_SA_VERSION.split('.'):
    raise ImportError('Version %s or later of SQLAlchemy required' % MIN_SA_VERSION)

from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.properties import SynonymProperty
from sqlalchemy.orm import compile_mappers, object_session, class_mapper
from sqlalchemy.orm.session import Session
from sqlalchemy.orm.scoping import ScopedSession
from sqlalchemy.orm.dynamic import DynamicAttributeImpl
from sqlalchemy.util import OrderedDict

from formalchemy import fields
from formalchemy import renderers
from formalchemy import fatypes

compile_mappers() # initializes InstrumentedAttributes


try:
    # 0.5
    from sqlalchemy.orm.attributes import manager_of_class
    def _get_attribute(cls, p):
        manager = manager_of_class(cls)
        return manager[p.key]
except ImportError:
    # 0.4
    def _get_attribute(cls, p):
        return getattr(cls, p.key)
    

def prettify(text):
    """
    Turn an attribute name into something prettier, for a default label where none is given.

    >>> prettify("my_column_name")
    'My column name'
    """
    return text.replace("_", " ").capitalize()



class SimpleMultiDict(dict):
    """
    Adds `getone`, `getall` methods to dict.  Assumes that values are either
    a string or a list of strings.
    """
    def getone(self, key):
        if key not in self:
            raise KeyError(key)
        v = dict.get(self, key)
        if v is None or isinstance(v, basestring) or isinstance(v, cgi.FieldStorage):
            return v
        return v[0]
    def getall(self, key):
        v = dict.get(self, key)
        if v is None:
            return []
        elif isinstance(v, basestring):
            return [v]
        return v


class ModelRenderer(object):
    """
    The `ModelRenderer` class is the superclass for all classes needing to deal 
    with `model` access and supporting rendering capabilities.
    """
    prettify = staticmethod(prettify)

    def __init__(self, model, session=None, data=None, prefix=None):
        """ 
        - `model`: 
              a SQLAlchemy mapped class or instance.  New object creation
              should be done by passing the class, which will need a default
              (no-parameter) constructor.  After construction or binding of
              the :class:`~formalchemy.forms.FieldSet`, the instantiated object will be available as
              the `.model` attribute.

        - `session=None`: 
              the session to use for queries (for relations). If `model` is associated
              with a session, that will be used by default. (Objects mapped with a
              `scoped_session
              <http://www.sqlalchemy.org/docs/05/session.html#contextual-thread-local-sessions>`_
              will always have a session. Other objects will
              also have a session if they were loaded by a Query.)

        - `data=None`: 
              dictionary-like object of user-submitted data to validate and/or
              sync to the `model`. Scalar attributes should have a single
              value in the dictionary; multi-valued relations should have a
              list, even if there are zero or one values submitted.  Currently,
              pylons request.params() objects and plain dictionaries are known
              to work.

        - `prefix=None`:
              the prefix to prepend to html name attributes. This is useful to avoid 
              field name conflicts when there are two fieldsets creating objects
              from the same model in one html page.  (This is not needed when
              editing existing objects, since the object primary key is used as part
              of the field name.)


        Only the `model` parameter is required.

        After binding, :class:`~formalchemy.forms.FieldSet`'s `model` attribute will always be an instance.
        If you bound to a class, `FormAlchemy` will call its constructor with no
        arguments to create an appropriate instance. 

        .. NOTE::

          This instance will not be added to the current session, even if you are using `Session.mapper`.

        All of these parameters may be overridden by the `bind` or `rebind`
        methods.  The `bind` method returns a new instance bound as specified,
        while `rebind` modifies the current :class:`~formalchemy.forms.FieldSet` and has
        no return value. (You may not `bind` to a different type of SQLAlchemy
        model than the initial one -- if you initially bind to a `User`, you
        must subsequently bind `User`'s to that :class:`~formalchemy.forms.FieldSet`.)

        Typically, you will configure a :class:`~formalchemy.forms.FieldSet` once in
        your common form library, then `bind` specific instances later for editing. (The
        `bind` method is thread-safe; `rebind` is not.)  Thus:

        load stuff:

        >>> from formalchemy.tests import FieldSet, User, session

        now, in `library.py`

        >>> fs = FieldSet(User)
        >>> fs.configure(options=[]) # put all configuration stuff here
        
        and in `controller.py`
        
        >>> from library import fs
        >>> user = session.query(User).first()
        >>> fs2 = fs.bind(user)
        >>> html = fs2.render()

        The `render_fields` attribute is an OrderedDict of all the `Field`'s
        that have been configured, keyed by name. The order of the fields
        is the order in `include`, or the order they were declared
        in the SQLAlchemy model class if no `include` is specified.

        The `_fields` attribute is an OrderedDict of all the `Field`'s
        the ModelRenderer knows about, keyed by name, in their
        unconfigured state.  You should not normally need to access
        `_fields` directly.
        
        (Note that although equivalent `Field`'s (fields referring to
        the same attribute on the SQLAlchemy model) will equate with
        the == operator, they are NOT necessarily the same `Field`
        instance.  Stick to referencing `Field`'s from their parent
        `FieldSet` to always get the "right" instance.)
        """
        self._fields = OrderedDict()
        self._render_fields = OrderedDict()
        self.model = self.session = None
        self.prefix = prefix

        if not model:
            raise Exception('model parameter may not be None')
        ModelRenderer.rebind(self, model, session, data)

        cls = isinstance(self.model, type) and self.model or type(self.model)
        try:
            class_mapper(cls)
        except:
            # this class is not managed by SA.  extract any raw Fields defined on it.
            keys = cls.__dict__.keys()
            keys.sort(lambda a, b: cmp(a.lower(), b.lower())) # 2.3 support
            for key in keys:
                field = cls.__dict__[key]
                if isinstance(field, fields.Field):
                    if field.name and field.name != key:
                        raise Exception('Fields in a non-mapped class have the same name as their attribute.  Do not manually give them a name.')
                    field.name = field.key = key
                    self.append(field)
            if not self._fields:
                raise Exception("not bound to a SA instance, and no manual Field definitions found")
        else:
            # SA class.
            # load synonyms so we can ignore them
            synonyms = set(p for p in class_mapper(cls).iterate_properties 
                           if isinstance(p, SynonymProperty))
            # attributes we're interested in
            attrs = []
            for p in class_mapper(cls).iterate_properties:
                attr = _get_attribute(cls, p)
                if ((isinstance(p, SynonymProperty) or attr.property.key not in (s.name for s in synonyms))
                    and not isinstance(attr.impl, DynamicAttributeImpl)):
                    attrs.append(attr)
            # sort relations last before storing in the OrderedDict
            L = [fields.AttributeField(attr, self) for attr in attrs]
            L.sort(lambda a, b: cmp(a.is_relation, b.is_relation)) # note, key= not used for 2.3 support
            self._fields.update((field.key, field) for field in L)

    def append(self, field):
        """Append a Field to the FieldSet.

        By default, this Field will be included in the rendered form or table.
        """
        if not isinstance(field, fields.Field):
            raise ValueError('Can only add Field objects; got %s instead' % field)
        field.parent = self
        _fields = self._render_fields or self._fields
        _fields[field.name] = field
        return self  # Cascade pattern

    def add(self, field):
        warnings.warn(DeprecationWarning('FieldSet.add is deprecated. Use FieldSet.append instead.'))
        self.append(field)

    def extend(self, fields):
        """Add a list of fields. By default, each Field will be included in the
        rendered form or table."""
        for field in fields:
            self.append(field)
        return self  # Cascade pattern

    def insert(self, field, new_field):
        """Insert a new field before an existing field"""
        fields_ = self._render_fields or self._fields
        if not isinstance(new_field, fields.Field):
            raise ValueError('Can only add Field objects; got %s instead' % field)
        if isinstance(field, fields.AbstractField):
            try:
                index = fields_.keys().index(field.name)
            except ValueError:
                raise ValueError('%s not in fields' % field.name)
        else:
            raise TypeError('field must be a Field. Got %r' % new_field)
        items = fields_.items()
        new_field.parent = self
        items.insert(index, (new_field.name, new_field))
        if self._render_fields:
            self._render_fields = OrderedDict(items)
        else:
            self._fields = OrderedDict(items)
        return self  # Cascade pattern
            
    def modify(self, *args):
        """Modify fields with their new value, without modifying the order"""
        for override in args:
            if override.name not in self._render_fields.keys():
                raise ValueError("Field %s isn't part of the fields to render, or you didn't configure you FieldSet yet" % override)
            for i, field in enumerate(self._render_fields):
                if field == override.key:
                    self._render_fields[field] = override
                    break
        return self

    def render_fields(self):
        """
        The set of attributes that will be rendered, as a (ordered)
        dict of `{fieldname: Field}` pairs. If you haven't called configure
        with exclude/include, then this will be the list of default Fields
        as found by introspecting the SQLAlchemy model.
        """
        if not self._render_fields:
            self._render_fields = OrderedDict([(field.key, field) for field in self._get_fields()])
        return self._render_fields
    render_fields = property(render_fields)

    def configure(self, pk=False, exclude=[], include=[], options=[]):
        """
        The `configure` method specifies a set of attributes to be rendered.
        By default, all attributes are rendered except primary keys and
        foreign keys.  But, relations `based on` foreign keys `will` be
        rendered.  For example, if an `Order` has a `user_id` FK and a `user`
        relation based on it, `user` will be rendered (as a select box of
        `User`'s, by default) but `user_id` will not.

        Parameters:
          * `pk=False`:
                set to True to include primary key columns
          * `exclude=[]`:
                an iterable of attributes to exclude.  Other attributes will
                be rendered normally
          * `include=[]`:
                an iterable of attributes to include.  Other attributes will
                not be rendered
          * `options=[]`:
                an iterable of modified attributes.  The set of attributes to
                be rendered is unaffected
          * `global_validator=None`:
                global_validator` should be a function that performs
                validations that need to know about the entire form.
          * `focus=True`:
                the attribute (e.g., `fs.orders`) whose rendered input element
                gets focus. Default value is True, meaning, focus the first
                element. False means do not focus at all.

        Only one of {`include`, `exclude`} may be specified.

        Note that there is no option to include foreign keys.  This is
        deliberate.  Use `include` if you really need to manually edit FKs.

        If `include` is specified, fields will be rendered in the order given
        in `include`.  Otherwise, fields will be rendered in alphabetical
        order.

        Examples: given a `FieldSet` `fs` bound to a `User` instance as a
        model with primary key `id` and attributes `name` and `email`, and a
        relation `orders` of related Order objects, the default will be to
        render `name`, `email`, and `orders`. To render the orders list as
        checkboxes instead of a select, you could specify::

        >>> from formalchemy.tests import FieldSet, User
        >>> fs = FieldSet(User)
        >>> fs.configure(options=[fs.orders.checkbox()])

        To render only name and email,

        >>> fs.configure(include=[fs.name, fs.email])
        
        or

        >>> fs.configure(exclude=[fs.orders])

        Of course, you can include modifications to a field in the `include`
        parameter, such as here, to render name and options-as-checkboxes:

        >>> fs.configure(include=[fs.name, fs.orders.checkbox()])
        """
        self._render_fields = OrderedDict([(field.key, field) for field in self._get_fields(pk, exclude, include, options)])

    def bind(self, model=None, session=None, data=None):
        """
        Return a copy of this FieldSet or Grid, bound to the given
        `model`, `session`, and `data`. The parameters to this method are the
        same as in the constructor.

        Often you will create and `configure` a FieldSet or Grid at application
        startup, then `bind` specific instances to it for actual editing or display.
        """
        if not (model or session or data):
            raise Exception('must specify at least one of {model, session, data}')
        if not model:
            if not self.model:
                raise Exception('model must be specified when none is already set')
            model = fields._pk(self.model) is None and type(self.model) or self.model
        # copy.copy causes a stacktrace on python 2.5.2/OSX + pylons.  unable to reproduce w/ simpler sample.
        mr = object.__new__(self.__class__)
        mr.__dict__ = dict(self.__dict__)
        # two steps so bind's error checking can work
        ModelRenderer.rebind(mr, model, session, data)
        mr._fields = OrderedDict([(key, renderer.bind(mr)) for key, renderer in self._fields.iteritems()])
        if self._render_fields:
            mr._render_fields = OrderedDict([(field.key, field) for field in
                                             [field.bind(mr) for field in self._render_fields.itervalues()]])
        return mr

    def rebind(self, model=None, session=None, data=None):
        """
        Like `bind`, but acts on this instance.  No return value.
        Not all parameters are treated the same; specifically, what happens if they are NOT specified is different:
           * if `model` is not specified, the old model is used
           * if `session` is not specified, FA tries to re-guess session from the model
           * if data is not specified, it is rebound to None.
        """
        original_model = model
        if model:
            if isinstance(model, type):
                try:
                    model = model()
                except:
                    raise Exception('%s appears to be a class, not an instance, but FormAlchemy cannot instantiate it.  (Make sure all constructor parameters are optional!)' % model)
                # take object out of session, if present
                try:
                    _obj_session = object_session(model)
                except AttributeError:
                    pass # non-SA object; doesn't need session
                else:
                    if _obj_session:
                        _obj_session.expunge(model)
            elif object_session(model):
                # for instances of mapped classes, require that the instance have a PK already
                try:
                    class_mapper(type(model))
                except:
                    pass
                else:
                    if fields._pk(model) is None:
                        raise Exception('Mapped instances to be bound must either have a primary key set or not be in a Session.  When creating a new object, bind the class instead [i.e., bind(User), not bind(User())]')
            if self.model and type(self.model) != type(model):
                raise ValueError('You can only bind to another object of the same type you originally bound to (%s), not %s' % (type(self.model), type(model)))
            self.model = model
            self._bound_pk = fields._pk(model)

        # Assign new data
        if data is None:
            self.data = None
        elif hasattr(data, 'getall') and hasattr(data, 'getone'):
            self.data = data
        else:
            try:
                self.data = SimpleMultiDict(data)
            except:
                raise Exception('unsupported data object %s.  currently only dicts and Paste multidicts are supported' % self.data)

        # Reset Field deserialization caches:
        _fields = self._render_fields or self._fields
        for f in _fields:
            self[f]._reset_cache()

        if session:
            if not isinstance(session, Session) and not isinstance(session, ScopedSession):
                raise ValueError('Invalid SQLAlchemy session object %s' % session)
            self.session = session
        elif model:
            if '_obj_session' in locals():
                # model may be a temporary object, expunged from its session -- grab the existing reference
                self.session = _obj_session
            else:
                try:
                    o_session = object_session(model)
                except AttributeError:
                    pass # non-SA object
                else:
                    if o_session:
                        self.session = o_session
        # if we didn't just instantiate (in which case object_session will be None), 
        # the session should be the same as the object_session
        if self.session and model == original_model:
            try:
                o_session = object_session(self.model)
            except AttributeError:
                pass # non-SA object
            else:
                if o_session and self.session is not o_session:
                    raise Exception('You may not explicitly bind to a session when your model already belongs to a different one')

    def sync(self):
        """
        Sync (copy to the corresponding attributes) the data passed to the constructor or `bind` to the `model`.
        """
        if self.data is None:
            raise Exception("No data bound; cannot sync")
        for field in self.render_fields.itervalues():
            field.sync()
        if self.session:
            self.session.add(self.model)

    def _raw_fields(self):
        return self._fields.values()
    
    def _get_fields(self, pk=False, exclude=[], include=[], options=[]):
        # sanity check
        if include and exclude:
            raise Exception('Specify at most one of include, exclude')

        # help people who meant configure(include=[X]) but just wrote configure(X), resulting in pk getting the positional argument
        if pk not in [True, False]:
            raise ValueError('pk option must be True or False, not %s' % pk)

        # verify that options that should be lists of Fields, are
        for iterable in ['include', 'exclude', 'options']:
            try:
                L = list(eval(iterable))
            except:
                raise ValueError('`%s` parameter should be an iterable' % iterable)
            for field in L:
                if not isinstance(field, fields.AbstractField):
                    raise TypeError('non-AbstractField object `%s` found in `%s`' % (field, iterable))
                if field not in self._fields.values():
                    raise ValueError('Unrecognized Field `%s` in `%s` -- did you mean to call append() first?' % (field, iterable))

        # if include is given, those are the fields used.  otherwise, include those not explicitly (or implicitly) excluded.
        if not include:
            ignore = list(exclude) # don't modify `exclude` directly to avoid surprising caller
            if not pk:
                ignore.extend([wrapper for wrapper in self._raw_fields() if wrapper.is_pk and not wrapper.is_collection])
            ignore.extend([wrapper for wrapper in self._raw_fields() if wrapper.is_raw_foreign_key])
            include = [field for field in self._raw_fields() if field not in ignore]
            
        # in the returned list, replace any fields in `include` w/ the corresponding one in `options`, if present.
        # this is a bit clunky because we want to 
        #   1. preserve the order given in `include`
        #   2. not modify `include` (or `options`) directly; that could surprise the caller
        options_dict = {} # create + update for 2.3's benefit
        options_dict.update(dict([(wrapper, wrapper) for wrapper in options]))
        L = []
        for wrapper in include:
            if wrapper in options_dict:
                L.append(options_dict[wrapper])
            else:
                L.append(wrapper)
        return L
    
    def __getattr__(self, attrname):
        try:
            return self._render_fields[attrname]
        except KeyError:
            try:
                return self._fields[attrname]
            except KeyError:
                raise AttributeError(attrname)

    __getitem__ = __getattr__

    def __setattr__(self, attrname, value):
        if attrname not in ('_fields', '__dict__', 'focus') and \
           (attrname in self._fields or isinstance(value, fields.AbstractField)):
            raise AttributeError('Do not set field attributes manually.  Use append() or configure() instead')
        object.__setattr__(self, attrname, value)

    def __delattr__(self, attrname):
        if attrname in self._render_fields:
            del self._render_fields[attrname]
        elif attrname in self._fields:
            raise RuntimeError("You try to delete a field but your form is not configured")
        else:
            raise AttributeError("field %s does not exist" % attrname)

    __delitem__ = __delattr__

    def render(self, **kwargs):
        raise NotImplementedError()


class EditableRenderer(ModelRenderer):
    default_renderers = {
        fatypes.String: renderers.TextFieldRenderer,
        fatypes.Integer: renderers.IntegerFieldRenderer,
        fatypes.Float: renderers.FloatFieldRenderer,
        fatypes.Numeric: renderers.FloatFieldRenderer,
        fatypes.Boolean: renderers.CheckBoxFieldRenderer,
        fatypes.DateTime: renderers.DateTimeFieldRenderer,
        fatypes.Date: renderers.DateFieldRenderer,
        fatypes.Time: renderers.TimeFieldRenderer,
        fatypes.Binary: renderers.FileFieldRenderer,
        'dropdown': renderers.SelectFieldRenderer,
        'checkbox': renderers.CheckBoxSet,
        'radio': renderers.RadioSet,
        'password': renderers.PasswordFieldRenderer,
        'textarea': renderers.TextAreaFieldRenderer,
    }
