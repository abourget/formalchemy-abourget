# Copyright (C) 2007 Alexandre Conrad, aconrad(dot.)tlv(at@)magic(dot.)fr
#
# This module is part of FormAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

import logging
logger = logging.getLogger('formalchemy.' + __name__)

from copy import copy, deepcopy

import helpers as h
import sqlalchemy.types as types
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.attributes import ScalarAttributeImpl, ScalarObjectAttributeImpl, CollectionAttributeImpl
import sqlalchemy.types as types
import base, validators

__all__ = ["TextField", "PasswordField", "HiddenField", "BooleanField",
    "FileField", "IntegerField", "DateTimeField", "DateField", "TimeField",
    "RadioSet", "SelectField", 'query_options']


class ModelField(object):
    """
    This should be the super class of all xField classes.

    This class takes a SQLAlchemy mapped class as first argument and the column
    name to process as second argument. It maps the column name as the field
    name and the column's value as the field's value.

    Methods:
      * `get_value(self)`
        Return the column's current value if not None, otherwise
        return the default column value if available.
      * `render(self)`
        Return generated HTML.
    """

    def __init__(self, attr, **kwargs):
        self.attr = attr
        self.attribs = kwargs
        
    def name(self):
        return self.attr.name
    name = property(name)
        
    def value(self):
        return self.attr.value
    value = property(value)

    def render(self):
        return h.text_field(self.name, value=self.value)

class TextField(ModelField):
    def __init__(self, attr, **kwargs):
        super(TextField, self).__init__(attr, **kwargs)
        self.length = attr.type.length

    def render(self):
        return h.text_field(self.name, value=self.value, maxlength=self.length, **self.attribs)

class PasswordField(TextField):
    def render(self):
        return h.password_field(self.name, value=self.value, maxlength=self.length, **self.attribs)

class TextAreaField(ModelField):
    def __init__(self, attr, size, **kwargs):
        super(TextAreaField, self).__init__(attr, **kwargs)
        self.size = size

    def render(self):
        if isinstance(self.size, basestring):
            return h.text_area(self.name, content=self.value, size=self.size, **self.attribs)
        else:
            # Will fail if not a 2-item list or tuple. 
            cols, rows = self.size
            return h.text_area(self.name, content=self.value, cols=cols, rows=rows, **self.attribs)

class HiddenField(ModelField):
    def render(self):
        return h.hidden_field(self.name, value=self.value, **self.attribs)

class BooleanField(ModelField):
    def render(self):
        # This is a browser hack to have a checkbox POSTed as False even if it wasn't
        # checked, as unchecked boxes are not POSTed. The hidden field should be *after* the checkbox.
        return h.check_box(self.name, True, checked=self.value, **self.attribs)

class FileField(ModelField):
    def render(self):
        # todo Do we need a value here ?
        return h.file_field(self.name, **self.attribs)

class IntegerField(ModelField):
    def render(self):
        return h.text_field(self.name, value=self.value, **self.attribs)

class ModelDateTimeField(ModelField):
    """
    The `ModelDateTimeField` class
    should be the super class for (Date|Time|DateTime)Field.
    """

    def __init__(self, attr, format, **kwargs):
        super(ModelDateTimeField, self).__init__(attr, **kwargs)
        self.format = format

    def get_value(self):
        value = super(ModelDateTimeField, self).get_value()
        if value is not None:
            return value.strftime(self.format)
        else:
            if not callable(self.default):
                return self.default

    def render(self):
        return h.text_field(self.name, value=self.value, **self.attribs)

class DateTimeField(ModelDateTimeField):
    pass

class DateField(ModelDateTimeField):
    pass

class TimeField(ModelDateTimeField):
    pass


def _extract_options(options):
    if isinstance(options, dict):
        options = options.items()
    for choice in options:
        # Choice is a list/tuple...
        if isinstance(choice, (list, tuple)):
            if len(choice) != 2:
                raise Exception('Options should consist of two items, a name and a value; found %d items in %r' % (len(choice, choice)))
            yield choice
        # ... or just a string.
        else:
            if not isinstance(choice, basestring):
                raise Exception('List, tuple, or string value expected as option (got %r)' % choice)
            yield (choice, choice)


class RadioSet(ModelField):
    widget = staticmethod(h.radio_button)
    def __init__(self, attr, options, **kwargs):
        super(RadioSet, self).__init__(attr)
        self.radios = []
        for choice_name, choice_value in _extract_options(options):
            radio = self.widget(self.name, choice_value, checked=self.value == choice_value, **kwargs)
            self.radios.append(radio + choice_name)
    def render(self):
        return h.tag("br").join(self.radios)

class CheckBoxSet(RadioSet):
    widget = staticmethod(h.check_box)


class SelectField(ModelField):
    def __init__(self, attr, options, **kwargs):
        self.options = options
        selected = kwargs.get('selected', None)
        super(SelectField, self).__init__(attr, **kwargs)
        self.selected = selected or self.value

    def render(self):
        return h.select(self.name, h.options_for_select(self.options, selected=self.selected), **self.attribs)

    
def _pk(instance):
    # Return the value of this instance's primary key.
    column = class_mapper(type(instance)).primary_key[0]
    return getattr(instance, column.key)


def query_options(query):
    """
    Return a list of tuples of `(item description, item pk)`
    for each item returned by the query, where `item description`
    is the result of str(item) and `item pk` is the item's primary key.
    
    This list is suitable for using as a value for `options` parameters.
    """
    return [(str(item), _pk(item)) for item in query.all()]


def _foreign_keys(property):
    # 0.4/0.5 compatibility fn
    try:
        return property.foreign_keys
    except AttributeError:
        return [r for l, r in property.synchronize_pairs]


class AbstractRenderer(object):
    """
    Contains the information necessary to render (and modify the rendering of)
    a form field
    """
    def __init__(self, parent):
        # the FieldSet (or any ModelRenderer) owning this instance
        self.parent = parent
        # what kind of Field to render this attribute as.  this will be autoguessed,
        # unless the user forces it with .dropdown, .checkbox, etc.
        self.render_as = None
        # other render options, such as size, multiple, etc.
        self.render_opts = {}
        # validator functions added with .validate()
        self.validators = []
        # errors found by _validate() (which runs implicit and explicit validators)
        self.errors = []
        # disabled or readonly
        self.modifier = None
        # label to use for the rendered field.  autoguessed if not specified by .label()
        self.label_text = None
        # default = not required; may be overriden to True by .required()
        self._required = False

    def __deepcopy__(self, memo):
        wrapper = copy(self)
        wrapper.render_opts = dict(self.render_opts)
        wrapper.validators = list(self.validators)
        wrapper.errors = list(self.errors)
        return wrapper
                        
    def is_raw_foreign_key(self):
        """True iff this attribute is a raw foreign key"""
        return False

    def is_pk(self):
        """True iff this attribute is a primary key"""
        return False

    def query(self, *args, **kwargs):
        """Perform a query in the parent's session"""
        return self.parent.session.query(*args, **kwargs)
    
    def _validate(self):
        self.errors = []

        try:
            value = self._unstr(self.parent.data.get(self.name))
        except validators.ValidationException, e:
            self.errors.append(e)
            return False

        L = list(self.validators)
        if self.is_required() and validators.required not in L:
            L.append(validators.required)
        for validator in L:
            try:
                validator(value)
            except validators.ValidationException, e:
                self.errors.append(e.message)
        return not self.errors

    def is_required(self):
        """True iff this attribute must be given a non-empty value"""
        return self._required
    
    def _unstr(self, st, force_scalar=False):
        """convert st (raw user data, or None) into the data type expected by attr"""
        # todo handle non-object collections from AdditionalRenderer
        if self.is_collection() and not force_scalar:
            return [self.query(self.collection_type()).get(self._unstr(id_st, True))
                    for id_st in st]
        if isinstance(self.type, types.Boolean):
            return st is not None
        if st is None:
            return None
        if isinstance(self.type, types.Integer):
            try:
                return int(st)
            except:
                raise validators.ValidationException('Value is not an integer')
        if isinstance(self.type, types.Float):
            try:
                return float(st)
            except:
                raise validators.ValidationException('Value is not a number')
        if isinstance(self.type, types.DateTime):
            # todo
            pass
        if isinstance(self.type, types.Date):
            # todo
            pass
        return st

    def model(self):
        return self.parent.model
    model = property(model)
    
    def bind(self, parent):
        """Return a copy of this attribute, bound to a different parent"""
        attr = deepcopy(self)
        attr.parent = parent
        return attr
    def validate(self, validator):
        attr = deepcopy(self)
        attr.validators.append(validator)
        return attr
    def required(self):
        attr = deepcopy(self)
        attr._required = True
        return attr
    def label(self, text):
        attr = deepcopy(self)
        attr.label_text = text
        return attr
    def disabled(self):
        attr = deepcopy(self)
        attr.modifier = 'disabled'
        return attr
    def readonly(self):
        attr = deepcopy(self)
        attr.modifier = 'readonly'
        return attr
    def hidden(self):
        attr = deepcopy(self)
        attr.render_as = HiddenField
        attr.render_opts = {}
        return attr
    def password(self):
        attr = deepcopy(self)
        attr.render_as = PasswordField
        attr.render_opts = {}
        return attr
    def textarea(self, size=None):
        attr = deepcopy(self)
        attr.render_as = TextAreaField
        attr.render_opts = {'size': size}
        return attr
    def radio(self, options=None):
        attr = deepcopy(self)
        attr.render_as = RadioSet
        if options is None:
            options = self.render_opts.get('options')
        attr.render_opts = {'options': options}
        return attr
    def checkbox(self, options=None):
        attr = deepcopy(self)
        attr.render_as = CheckBoxSet
        if options is None:
            options = self.render_opts.get('options')
        attr.render_opts = {'options': options}
        return attr
    def dropdown(self, options=None, multiple=False):
        attr = deepcopy(self)
        attr.render_as = SelectField
        if options is None:
            options = self.render_opts.get('options')
        attr.render_opts = {'multiple': multiple, 'options': options}
        return attr

    def _get_render_as(self):
        if isinstance(self.type, types.String):
            return TextField
        elif isinstance(self.type, types.Integer):
            return IntegerField
        elif isinstance(self.type, types.Boolean):
            return BooleanField
        elif isinstance(self.type, types.DateTime):
            return DateTimeField
        elif isinstance(self.type, types.Date):
            return DateField
        elif isinstance(self.type, types.Time):
            return TimeField
        elif isinstance(self.type, types.Binary):
            return FileField
        return ModelField
    
    def render(self, **html_options):
        """
        Render this attribute as HTML.
        
        `html_options` are not used by the default template, but are
        provided to make more customization possible in custom templates
        """
        opts = dict(self.render_opts)
        opts.update(html_options)
        return self.render_as(self, readonly=self.modifier=='readonly', disabled=self.modifier=='disabled', **opts).render()


class AdditionalRenderer(AbstractRenderer):
    """
    Renderer for a manually-added form field
    """
    def __init__(self, parent, name, type, value):
        AbstractRenderer.__init__(self, parent)
        self.type = type
        self.name = name
        self.value = value
        
    def key(self):
        return self.name
    key = property(key)

    def is_collection(self):
        return self.render_opts.get('multiple', False)
    
    def value_str(self):
        if self.is_collection():
            return [str(item) for item in self.value]
        return str(self.value)

    def sync(self):
        """Set the attribute's value in `model` to the value given in `data`"""
        self.value = self._unstr(self.parent.data.get(self.name))
            
    def __repr__(self):
        return 'AttributeRenderer(%s)' % self.name
    
    def render(self, **html_options):
        if not self.render_as:
            self.render_as = self._get_render_as()
        return AbstractRenderer.render(self, **html_options)

    def __eq__(self, other):
        # we override eq so that when we configure with options=[...], we can match the renders in options
        # with the ones that were generated at FieldSet creation time
        try:
            return self.name is other.name and self.model is other.model
        except (AttributeError, ValueError):
            return False
    def __hash__(self):
        return hash(self.name)


class AttributeRenderer(AbstractRenderer):
    """
    Renderer for an SQLAlchemy attribute.
    """
    def __init__(self, instrumented_attribute, parent):
        AbstractRenderer.__init__(self, parent)
        # we rip out just the parts we care about from InstrumentedAttribute.
        # impl is the AttributeImpl.  So far all we care about there is ".key,"
        # which is the name of the attribute in the mapped class.
        self._impl = instrumented_attribute.impl
        # property is the PropertyLoader which handles all the interesting stuff.
        # mapper, columns, and foreign keys are all located there.
        self._property = instrumented_attribute.property
        # smarter default "required" value
        self._required = (not self.is_collection() and not self._column.nullable)
            
    def is_raw_foreign_key(self):
        try:
            return _foreign_keys(self._property.columns[0])
        except AttributeError:
            return False
        
    def is_pk(self):
        return self._column.primary_key
    
    def type(self):
        return self._column.type
    type = property(type)

    def _column(self):
        # todo this does not allow handling composite attributes (PKs or FKs)
        if isinstance(self._impl, ScalarObjectAttributeImpl):
            # If the attribute is a foreign key, return the Column that this
            # attribute is mapped from -- e.g., .user -> .user_id. 
            return _foreign_keys(self._property)[0]
        elif isinstance(self._impl, ScalarAttributeImpl):
            # normal property, mapped to a single column from the main table
            return self._property.columns[0]
        else:
            # collection -- use the mapped class's PK
            assert isinstance(self._impl, CollectionAttributeImpl)
            return self._property.mapper.primary_key[0]
    _column = property(_column)
    
    def key(self):
        """The name of the attribute in the class"""
        return self._impl.key
    key = property(key)

    def name(self):
        """ 
        The name of the form input. usually the same as the column name, except for
        multi-valued SA relation properties. For example, for order.user,
        name will be user_id (assuming that is indeed the name of the foreign
        key to users). 
        """
        if self.is_collection():
            return self.key
        return self._column.name
    name = property(name)

    def is_collection(self):
        """True iff this is a multi-valued (one-to-many or many-to-many) SA relation"""
        return isinstance(self._impl, CollectionAttributeImpl)
    
    def collection_type(self):
        """The type of object in the collection (e.g., `User`).  Calling this is only valid when `is_collection()` is True"""
        return self._property.mapper.class_
    
    def value(self):
        """
        The value of this attribute: use the corresponding value in the bound `data`,
        if any; otherwise, use the value in the bound `model`.  If there is still no
        value, use the default defined on the corresponding `Column`.
        
        For collections,
        a list of the primary key values of the items in the collection is returned.
        """
        if self.parent.data is not None and self.name in self.parent.data:
            v = self._unstr(self.parent.data[self.name])
        else:
            v = getattr(self.model, self.name)
        if self.is_collection():
            return [_pk(item) for item in v]
        if v is not None:
            return v
        if self._column.default:
            if callable(self._column.default.arg):
                logger.info('Ignoring callable default value for %s' % self)
            else:
                return self._column.default
        return None
    value = property(value)
    
    def value_str(self):
        """A string representation of `value` for use in non-editable contexts (so we don't check 'data')"""
        if self.is_collection():
            L = getattr(self.model, self.key)
            return ','.join([str(item) for item in L])
        else:
            return str(getattr(self.model, self.key))
        
    def sync(self):
        """Set the attribute's value in `model` to the value given in `data`"""
        setattr(self.model, self.name, self._unstr(self.parent.data.get(self.name)))
            
    def __eq__(self, other):
        # we override eq so that when we configure with options=[...], we can match the renders in options
        # with the ones that were generated at FieldSet creation time
        try:
            return self._impl is other._impl and self.model is other.model
        except (AttributeError, ValueError):
            return False
    def __hash__(self):
        return hash(self._impl)
    
    def __repr__(self):
        return 'AttributeRenderer(%s)' % self.key
    
    def render(self, **html_options):
        if not self.render_as:
            self.render_as = self._get_render_as()
        if isinstance(self._impl, ScalarObjectAttributeImpl) or self.is_collection():
            if not self.render_opts.get('options'):
                # todo this does not handle primaryjoin (/secondaryjoin) alternate join conditions
                fk_cls = self.collection_type()
                fk_pk = class_mapper(fk_cls).primary_key[0]
                q = self.parent.session.query(fk_cls).order_by(fk_pk)
                self.render_opts['options'] = query_options(q)
                logger.debug('options for %s are %s' % (self.name, self.render_opts['options']))
        if isinstance(self.type, types.Boolean) and not self.render_opts.get('options') and self.render_as in [SelectField, RadioSet]:
            self.render_opts['options'] = [('True', True), ('False', False)]
        return AbstractRenderer.render(self, **html_options)

    def _get_render_as(self):
        if isinstance(self._impl, ScalarObjectAttributeImpl):
            return SelectField
        if self.is_collection():
            self.render_opts['multiple'] = True
            if 'size' not in self.render_opts:
                self.render_opts['size'] = 5
            return SelectField
        return AbstractRenderer._get_render_as(self)
