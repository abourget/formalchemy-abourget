# Copyright (C) 2007 Alexandre Conrad, alexandre (dot) conrad (at) gmail (dot) com
# Copyright (C) 2009 Alexandre Bourget, alex@bourget.cc
#
# This module is part of FormAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php



import cgi
import datetime

from formalchemy import helpers as h
from formalchemy.i18n import get_translator
from formalchemy.i18n import _
from formalchemy import fatypes, validators
from formalchemy.utils import stringify
# Removed to prevent circular imports
#from formalchemy.fields import AbstractField

__all__ = ['FieldRenderer', 'SelectFieldRenderer',
           'TextFieldRenderer', 'TextAreaFieldRenderer',
           'PasswordFieldRenderer', 'HiddenFieldRenderer',
           'DateFieldRenderer', 'TimeFieldRenderer',
           'DateTimeFieldRenderer', 'EscapingReadonlyRenderer',
           'CheckBoxFieldRenderer', 'CheckBoxSet',
           'FileFieldRenderer']



########################## RENDERER STUFF ############################



def iterable(item):
    try:
        iter(item)
    except:
        return False
    return True

class FieldRenderer(object):
    """
    This should be the super class of all Renderer classes.

    Renderers generate the html corresponding to a single Field,
    and are also responsible for deserializing form data into
    Python objects.

    Subclasses should override `render` and `deserialize`.
    See their docstrings for details.
    """
    def __init__(self, field):
        self.field = field
        # REMOVED: FieldRender.__init__ only called by AbstractField.renderer
        # itself, so there's no need to check over here.
        #assert isinstance(self.field, AbstractField)

    def name(self):
        """Name of rendered input element.

        The `name` of a field will always look like:
          [fieldset_prefix-]ModelName-[pk]-fieldname
        
        The fieldset_prefix is defined when instantiating the
        `FieldSet` object, by passing the `prefix=` keyword argument.

        The `ModelName` is taken by introspection from the model
        passed in at that same moment.

        The `pk` is the primary key of the object being edited.
        If you are creating a new object, then the `pk` is an
        empty string.

        The `fieldname` is, well, the field name.

        .. note::
         This method as the direct consequence that you can not `create`
         two objects of the same class, using the same FieldSet, on the
         same page. You can however, create more than one object
         of a certain class, provided that you create multiple FieldSet
         instances and pass the `prefix=` keyword argument.
         
         Otherwise, FormAlchemy deals very well with editing multiple
         existing objects of same/different types on the same page,
         without any name clash. Just be careful with multiple object
         creation.

        When creating your own Renderer objects, use `self.name` to
        get the field's `name` HTML attribute, both when rendering
        and deserializing.
        """
        clsname = self.field.model.__class__.__name__
        pk = self.field.parent._bound_pk
        assert pk != ''
        if isinstance(pk, basestring) or not iterable(pk):
            pk_string = stringify(pk)
        else:
            # remember to use a delimiter that can be used in the DOM (specifically, no commas).
            # we don't have to worry about escaping the delimiter, since we never try to
            # deserialize the generated name.  All we care about is generating unique
            # names for a given model's domain.
            pk_string = u'_'.join([stringify(k) for k in pk])

        components = [clsname, pk_string, self.field.name]
        if self.field.parent.prefix:
            components.insert(0, self.field.parent.prefix)
        return u"-".join(components)
    name = property(name)

    def _value(self):
        """
        Submitted value, or field value converted to string.
        Return value is always either None or a string.
        """
        if not self.field.is_readonly() and self.params is not None:
            # submitted value.  do not deserialize here since that requires valid data, which we might not have
            v = self._serialized_value() 
        else:
            v = None
        # empty field will be '' -- use default value there, too
        return v or self._model_value_as_string()
    _value = property(_value)

    def _model_value_as_string(self):
        if self.field.model_value is None:
            return None
        if self.field.is_collection:
            return [self.stringify_value(v) for v in self.field.model_value]
        else:
            return self.stringify_value(self.field.model_value)

    def get_translator(self, **kwargs):
        """return a GNUTranslations object in the most convenient way
        """
        if 'F_' in kwargs:
            return kwargs.pop('F_')
        if 'lang' in kwargs:
            lang = kwargs.pop('lang')
        else:
            lang = 'en'
        return get_translator(lang=lang).gettext

    def errors(self):
        """Return the errors on the FieldSet if any. Useful to know
        if you're redisplaying a form, or showing up a fresh one.
        """
        return self.field.parent.errors
    errors = property(errors)

    def render(self, **kwargs):
        """
        Render the field.  Use `self.name` to get a unique name for the
        input element and id.  `self._value` may also be useful if
        you are not rendering multiple input elements.

        When rendering, you can verify `self.errors` to know
        if you are rendering a new form, or re-displaying a form with
        errors. Knowing that, you could select the data either from
        the model, or the web form submission.
        """
        raise NotImplementedError()

    def render_readonly(self, **kwargs):
        """render a string representation of the field value"""
        value = self.field.raw_value
        if value is None:
            return ''
        if self.field.is_scalar_relation:
            q = self.field.query(self.field.relation_type())
            v = q.get(value)
            return stringify(v)
        if isinstance(value, list):
            return u', '.join([stringify(item) for item in value])
        if isinstance(value, unicode):
            return value
        return stringify(value)

    def params(self):
        """This gives access to the POSTed data, as received from
        the web user. You should call `.getone`, or `.getall` to 
        retrieve a single value or multiple values for a given
        key.

        For example, when coding a renderer:

        >>> vals = self.params.getall(self.name)  #doctest: +SKIP

        will catch all the values for the renderer's form entry.
        """
        return self.field.parent.data
    params = property(params)

    # DEPRECATED, for backwards compatibility
    def _params(self):
        """DEPRECATED: for backwards compatibility only."""
        import warnings
        warnings.warn('FieldRenderer._params is deprecated. Use '\
                          'FieldRenderer.params instead')
        return self.params
    _params = property(_params)

    def _serialized_value(self):
        """
        Returns the appropriate value to deserialize for field's
        datatype, from the user-submitted data.  Only called
        internally, so, if you are overriding `deserialize`,
        you can use or ignore `_serialized_value` as you please.

        This is broken out into a separate method so multi-input
        renderers can stitch their values back into a single one
        to have that can be handled by the default deserialize.

        Do not attempt to deserialize here; return value should be a
        string (corresponding to the output of `str` for your data
        type), or for a collection type, a a list of strings,
        or None if no value was submitted for this renderer.

        The default _serialized_value returns the submitted value(s)
        in the input element corresponding to self.name.
        """
        if self.field.is_collection:
            return self.params.getall(self.name)
        return self.params.getone(self.name)

    def value(self):
        """Return the current value for this field, either from the database
        or from the result of the validation, if any value was successfully
        parsed.

        This value should always look like if it came from the database model.
        It should be some python value (eg., datetime object). It can also come
        from the deserialize() function, or the cached validation results."""
        return self.field.value
    value = property(value)

    def value_objects(self):
        """Same as `value`, except returns a list of objects instead of 
        primary keys, when working with ForeignKeys.

        Use this when your `deserialize` or `render` functions manipulates
        ForeignKey objects; adding, removing or changing display according
        to their contents.
        """
        return self.field.value_objects
    value_objects = property(value_objects)

    def deserialize(self):
        """
        Turns the user-submitted data into a Python value.

        The raw data received from the web can be accessed via
        `self.params`. This dict-like object usually accepts the
        `getone()` and `getall()` method calls.

        For SQLAlchemy
        collections, return a list of primary keys, and !FormAlchemy
        will take care of turning that into a list of objects.
        For manually added collections, return a list of values.

        You will need to override this in a child Renderer object
        if you want to mangle the data from your web form, before
        it reaches your database model. For example, if your render()
        method displays a select box filled with items you got from a
        CSV file or another source, you will need to decide what to do
        with those values when it's time to save them to the database
        -- or is this field going to determine the hashing algorithm
        for your password ?.

        This function should return the value that is going to be
        assigned to the model *and* used in the place of the model
        value if there was an error with the form.

        .. note::
         Note that this function will be called *twice*, once when
         the fieldset is `.validate()`'d -- with it's value only tested,
         and a second time when the fieldset is `.sync()`'d -- and it's
         value assigned to the model. Also note that deserialize() can
         also raise a ValidationError() exception if it finds some
         errors converting it's values.
        """
        if self.field.is_collection:
            return [self._deserialize(subdata) for subdata in self._serialized_value()]
        return self._deserialize(self._serialized_value())

    def _deserialize(self, data):
        if isinstance(self.field.type, fatypes.Boolean):
            if data is not None:
                if data.lower() in ['1', 't', 'true', 'yes']: return True
                if data.lower() in ['0', 'f', 'false', 'no']: return False
        if data is None or data == self.field._null_option[1]:
            return None
        if isinstance(self.field.type, fatypes.Integer):
            return validators.integer(data, self)
        if isinstance(self.field.type, fatypes.Float):
            return validators.float_(data, self)
        if isinstance(self.field.type, fatypes.Numeric):
            if self.field.type.asdecimal:
                return validators.decimal_(data, self)
            else:
                return validators.float_(data, self)

        def _date(data):
            if data == 'YYYY-MM-DD' or data == '-MM-DD' or not data.strip():
                return None
            try:
                return datetime.date(*[int(st) for st in data.split('-')])
            except:
                raise validators.ValidationError('Invalid date')
        def _time(data):
            if data == 'HH:MM:SS' or not data.strip():
                return None
            try:
                return datetime.time(*[int(st) for st in data.split(':')])
            except:
                raise validators.ValidationError('Invalid time')

        if isinstance(self.field.type, fatypes.Date):
            return _date(data)
        if isinstance(self.field.type, fatypes.Time):
            return _time(data)
        if isinstance(self.field.type, fatypes.DateTime):
            data_date, data_time = data.split(' ')
            dt, tm = _date(data_date), _time(data_time)
            if dt is None and tm is None:
                return None
            elif dt is None or tm is None:
                raise validators.ValidationError('Incomplete datetime')
            return datetime.datetime(dt.year, dt.month, dt.day, tm.hour, tm.minute, tm.second)

        return data
    def stringify_value(self, v):
        return stringify(v, null_value=self.field._null_option[1])

class EscapingReadonlyRenderer(FieldRenderer):
    """
    In readonly mode, html-escapes the output of the default renderer
    for this field type.  (Escaping is not performed by default because
    it is sometimes useful to have the renderer include raw html in its
    output.  The FormAlchemy admin app extension for Pylons uses this,
    for instance.)
    """
    def __init__(self, field):
        FieldRenderer.__init__(self, field)
        self._renderer = field._get_renderer()(field)

    def render(self, **kwargs):
        return self._renderer.render(**kwargs)

    def render_readonly(self, **kwargs):
        return h.html_escape(self._renderer.render_readonly(**kwargs))


class TextFieldRenderer(FieldRenderer):
    """render a field as a text field"""
    def length(self):
        return self.field.type.length
    length = property(length)

    def render(self, **kwargs):
        return h.text_field(self.name, value=self._value, maxlength=self.length, **kwargs)


class IntegerFieldRenderer(FieldRenderer):
    """render an integer as a text field"""
    def render(self, **kwargs):
        return h.text_field(self.name, value=self._value, **kwargs)


class FloatFieldRenderer(FieldRenderer):
    """render a float as a text field"""
    def render(self, **kwargs):
        return h.text_field(self.name, value=self._value, **kwargs)


class PasswordFieldRenderer(TextFieldRenderer):
    """Render a password field"""
    def render(self, **kwargs):
        return h.password_field(self.name, value=self._value, maxlength=self.length, **kwargs)
    def render_readonly(self):
        return '*'*6

class TextAreaFieldRenderer(FieldRenderer):
    """render a field as a textarea"""
    def render(self, **kwargs):
        if isinstance(kwargs.get('size'), tuple):
            kwargs['size'] = 'x'.join([str(i) for i in kwargs['size']])
        return h.text_area(self.name, content=self._value, **kwargs)


class HiddenFieldRenderer(FieldRenderer):
    """render a field as an hidden field"""
    def render(self, **kwargs):
        return h.hidden_field(self.name, value=self._value, **kwargs)
    def render_readonly(self):
        return ''


class CheckBoxFieldRenderer(FieldRenderer):
    """render a boolean value as checkbox field"""
    def render(self, **kwargs):
        return h.check_box(self.name, True, checked=_simple_eval(self._value or ''), **kwargs)
    def _serialized_value(self):
        if self.name not in self.params:
            return None
        return FieldRenderer._serialized_value(self)
    def deserialize(self):
        if self._serialized_value() is None:
            return False
        return FieldRenderer.deserialize(self)

class FileFieldRenderer(FieldRenderer):
    """render a file input field"""
    remove_label = _('Remove')
    def __init__(self, *args, **kwargs):
        FieldRenderer.__init__(self, *args, **kwargs)
        self._data = None # caches FieldStorage data
        self._filename = None

    def render(self, **kwargs):
        if self.field.model_value:
            checkbox_name = '%s--remove' % self.name
            return '%s %s %s' % (
                   h.file_field(self.name, **kwargs),
                   h.check_box(checkbox_name),
                   h.label(self.remove_label, for_=checkbox_name))
        else:
            return h.file_field(self.name, **kwargs)

    def get_size(self):
        value = self.field.raw_value
        if value is None:
            return 0
        return len(value)

    def readable_size(self):
        length = self.get_size()
        if length == 0:
            return '0 KB'
        if length <= 1024:
            return '1 KB'
        if length > 1048576:
            return '%0.02f MB' % (length / 1048576.0)
        return '%0.02f KB' % (length / 1024.0)

    def render_readonly(self, **kwargs):
        """
        render only the binary size in a human readable format but you can
        override it to whatever you want
        """
        return self.readable_size()

    def deserialize(self):
        data = FieldRenderer.deserialize(self)
        if isinstance(data, cgi.FieldStorage):
            if data.filename:
                # FieldStorage can only be read once so we need to cache the
                # value since FA call deserialize during validation and
                # synchronisation
                if self._data is None:
                    self._filename = data.filename
                    self._data = data.file.read()
                data = self._data
            else:
                data = None
        checkbox_name = '%s--remove' % self.name
        if not data and not self.params.has_key(checkbox_name):
            data = getattr(self.field.model, self.field.name)
        return data is not None and data or ''

# for when and/or is not safe b/c first might eval to false
def _ternary(condition, first, second):
    if condition:
        return first()
    return second()

class DateFieldRenderer(FieldRenderer):
    """Render a date field"""
    format = '%Y-%m-%d'
    edit_format = 'm-d-y'
    def render_readonly(self, **kwargs):
        value = self.field.raw_value
        return value and value.strftime(self.format) or ''
    def _render(self, **kwargs):
        data = self.params
        F_ = self.get_translator(**kwargs)
        month_options = [(F_('Month'), 'MM')] + [(F_('month_%02i' % i), str(i)) for i in xrange(1, 13)]
        day_options = [(F_('Day'), 'DD')] + [(i, str(i)) for i in xrange(1, 32)]
        mm_name = self.name + '__month'
        dd_name = self.name + '__day'
        yyyy_name = self.name + '__year'
        mm = _ternary((data is not None and mm_name in data), lambda: data[mm_name],  lambda: str(self.field.model_value and self.field.model_value.month))
        dd = _ternary((data is not None and dd_name in data), lambda: data[dd_name], lambda: str(self.field.model_value and self.field.model_value.day))
        # could be blank so don't use and/or construct
        if data is not None and yyyy_name in data:
            yyyy = data[yyyy_name]
        else:
            yyyy = str(self.field.model_value and self.field.model_value.year or 'YYYY')
        selects = dict(
                m=h.select(mm_name, h.options_for_select(month_options, selected=mm), **kwargs),
                d=h.select(dd_name, h.options_for_select(day_options, selected=dd), **kwargs),
                y=h.text_field(yyyy_name, value=yyyy, maxlength=4, size=4, **kwargs))
        value = [selects.get(l) for l in self.edit_format.split('-')]
        return ' '.join(value)
    def render(self, **kwargs):
        return h.content_tag('span', self._render(**kwargs), id=self.name)

    def _serialized_value(self):
        return '-'.join([self.params.getone(self.name + '__' + subfield) for subfield in ['year', 'month', 'day']])


class TimeFieldRenderer(FieldRenderer):
    """Render a time field"""
    format = '%H:%M:%S'
    def render_readonly(self, **kwargs):
        value = self.field.raw_value
        return value and value.strftime(self.format) or ''
    def _render(self, **kwargs):
        data = self.params
        hour_options = ['HH'] + [(i, str(i)) for i in xrange(24)]
        minute_options = ['MM' ] + [(i, str(i)) for i in xrange(60)]
        second_options = ['SS'] + [(i, str(i)) for i in xrange(60)]
        hh_name = self.name + '__hour'
        mm_name = self.name + '__minute'
        ss_name = self.name + '__second'
        hh = _ternary((data is not None and hh_name in data), lambda: data[hh_name], lambda: str(self.field.model_value and self.field.model_value.hour))
        mm = _ternary((data is not None and mm_name in data), lambda: data[mm_name], lambda: str(self.field.model_value and self.field.model_value.minute))
        ss = _ternary((data is not None and ss_name in data), lambda: data[ss_name], lambda: str(self.field.model_value and self.field.model_value.second))
        return h.select(hh_name, h.options_for_select(hour_options, selected=hh), **kwargs) \
               + ':' + h.select(mm_name, h.options_for_select(minute_options, selected=mm), **kwargs) \
               + ':' + h.select(ss_name, h.options_for_select(second_options, selected=ss), **kwargs)
    def render(self, **kwargs):
        return h.content_tag('span', self._render(**kwargs), id=self.name)

    def _serialized_value(self):
        return ':'.join([self.params.getone(self.name + '__' + subfield) for subfield in ['hour', 'minute', 'second']])


class DateTimeFieldRenderer(DateFieldRenderer, TimeFieldRenderer):
    """Render a date time field"""
    format = '%Y-%m-%d %H:%M:%S'
    def render(self, **kwargs):
        return h.content_tag('span', DateFieldRenderer._render(self, **kwargs) + ' ' + TimeFieldRenderer._render(self, **kwargs), id=self.name)

    def _serialized_value(self):
        return DateFieldRenderer._serialized_value(self) + ' ' + TimeFieldRenderer._serialized_value(self)


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


class RadioSet(FieldRenderer):
    """render a field as radio"""
    widget = staticmethod(h.radio_button)
    format = '%(field)s%(label)s'
    
    def _serialized_value(self):
        if self.name not in self.params:
            return None
        return FieldRenderer._serialized_value(self)

    def _is_checked(self, choice_value):
        return self._value == stringify(choice_value)

    def render(self, options, **kwargs):
        self.radios = []
        for i, (choice_name, choice_value) in enumerate(_extract_options(options)):
            choice_id = '%s_%i' % (self.name, i)
            radio = self.widget(self.name, choice_value, id=choice_id,
                                checked=self._is_checked(choice_value), **kwargs)
            label = h.content_tag('label', choice_name, for_=choice_id)
            self.radios.append(self.format % dict(field=radio,
                                                  label=label))
        return h.tag("br").join(self.radios)


class CheckBoxSet(RadioSet):
    widget = staticmethod(h.check_box)

    def _serialized_value(self):
        if self.name not in self.params:
            return []
        return FieldRenderer._serialized_value(self)

    def _is_checked(self, choice_value):
        return stringify(choice_value) in self._value


class SelectFieldRenderer(FieldRenderer):
    """render a field as select"""
    def _serialized_value(self):
        if self.name not in self.params:
            if self.field.is_collection:
                return []
            return None
        return FieldRenderer._serialized_value(self)

    def render(self, options, **kwargs):
        L = list(options)
        if len(L) > 0:
            if len(L[0]) == 2:
                L = [(k, self.stringify_value(v)) for k, v in L]
            else:
                L = [stringify(k) for k in L]
        return h.select(self.name, h.options_for_select(L, selected=self._value), **kwargs)


