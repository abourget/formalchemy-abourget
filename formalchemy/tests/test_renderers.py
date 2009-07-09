from formalchemy.tests import *
from formalchemy.renderers import *
import datetime


__doc__ = r"""
Let's test the behavior of a Field element, returning a modified copy of itself
when we call some methods on it:

  >>> fs = FieldSet(User)
  >>> fs.password
  AttributeField(password)
  >>> fs.password.renderer
  <TextFieldRenderer for AttributeField(password)>

Two tests to show that with_renderer doesn't change the Field in place.

  >>> fs.password.with_renderer(PasswordFieldRenderer).renderer
  <PasswordFieldRenderer for AttributeField(password)>
  >>> fs.password.renderer
  <TextFieldRenderer for AttributeField(password)>
  
Now let's try to modify it. First, we call configure(), so that the fields of
the model are "copied" to the `render_fields` - the fields to actually be
rendered.

  >>> fs.configure()
  >>> fs.modify(fs.password.with_renderer(PasswordFieldRenderer))  #doctest: +ELLIPSIS
  <formalchemy.tests.FieldSet object ...>
  >>> fs.password.renderer
  <PasswordFieldRenderer for AttributeField(password)>

# Test append - tested in test_fieldset_api.py

# Test insert_after
Continuing with this `fs`:

  >>> fs.append(Field('passwd1'))  #doctest: +ELLIPSIS
  <formalchemy.tests.FieldSet object ...>
  >>> 

# Test insert_at_index
# Test caching system, including rebind
#   see http://groups.google.com/group/formalchemy/browse_thread/thread/958887f41ed4dd71
# Test .value_objects
# Test passwords_match
# Test with a standard/best way to create a FieldSet (custom Class, function that generates a FieldSet ?)
# Test global_validators, being passed to configure() or remove it
  # take from my changeset that fixed configure(), there were some good things
  # in there anyway.
# Test the new configure() with plenty of tests, incrementally
# Test focus on configure(), readonly with previous settings (set in __init__ ?)

# Test set() (rename from update)
# Test get()
#   on renderers, and fields
# Pylons Admin app configurable
#   see http://groups.google.com/group/formalchemy/browse_thread/thread/a4dd3fa2ffd3b184
# Remove with_metadata (superseded by set()/get())
# Change with_html to html()
# Change Field in-place
# Document (in examples) how to create stacks, with custom settings
#   Example of how to use set(help=u"blah") and show it in the template
"""

if __name__ == '__main__':
    import doctest
    doctest.testmod()
