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
  >>> fs.modify(fs.password.with_renderer(PasswordFieldRenderer))
  <FieldSet (configured) with ['email', 'password', 'name', 'orders']>
  >>> fs.password.renderer
  <PasswordFieldRenderer for AttributeField(password)>

Continuing with this `fs`, testing `insert_after`:

  >>> fs.append(Field('passwd1'))
  <FieldSet (configured) with ['email', 'password', 'name', 'orders', 'passwd1']>
  >>> fs.insert_after('name', fs.passwd1)
  <FieldSet (configured) with ['email', 'password', 'name', 'passwd1', 'orders']>
  >>> fs._fields.keys()
  ['id', 'email', 'password', 'name', 'orders']
  >>> fs._render_fields.keys()
  ['email', 'password', 'name', 'passwd1', 'orders']

Kind of the same thing with insert_at_index:

  >>> fs.append(Field('passwd2'))
  <FieldSet (configured) with ['email', 'password', 'name', 'passwd1', 'orders', 'passwd2']>
  >>> fs.insert_at_index(4, fs.passwd2)
  <FieldSet (configured) with ['email', 'password', 'name', 'passwd1', 'passwd2', 'orders']>
  >>> fs._render_fields.keys()
  ['email', 'password', 'name', 'passwd1', 'passwd2', 'orders']

Stress-test the bind() / rebind() and caching engine:

  >>> post_data = [('User--passwd1', 'pass'), ('User--passwd2', 'pass'),
  ...              ('User--name', 'blah'), ('User--email', 'blah@example.com')]
  >>> fs2 = UserFieldSet().bind(data=post_data or None)
  >>> fs2.validate()
  True
  >>> fs2.sync()
  >>> fs2.model.password = fs2.passwd1.value

After rebind:

  >>> post_data = [('User--passwd1', 'other'), ('User--passwd2', 'other'),
  ...              ('User--name', 'blah'), ('User--email', 'blah@example.com')]
  >>> fs2.rebind(data=post_data)
  >>> fs2.validate()
  True
  >>> fs2.sync()
  >>> assert fs2.passwd1.value == 'other', "Rebind didn't clear cache"

# Test set/get in the Field and the Renderer.
#   - Show set() modifies IN-PLACE

Test set/get

  >>> fs = FieldSet(User.query.first())
  >>> fs.name.set(label=u"Your name", help=u"Just enter your name")
  AttributeField(name)
  >>> fs.name.get('label')
  u'Your name'
  >>> fs.name.get('help')
  u'Just enter your name'
  >>> fs.name.get('some_other', u"Default value")
  u'Default value'
  >>> fs.name.renderer
  <TextFieldRenderer for AttributeField(name)>
  >>> fs.name.renderer.get('label') == fs.name.get('label')
  True
  >>> fs.name.set(validate=lambda x: x)
  AttributeField(name)
  >>> fs.name.validators  #doctest: +ELLIPSIS
  [<function <lambda> at ...>]
  >>> fs.name.set(validate=lambda y: y)
  AttributeField(name)
  >>> fs.name.validators  #doctest: +ELLIPSIS
  [<function <lambda> at ...>, <function <lambda> at ...>]

Test the validate/extend combination:

  >>> fs.name.set(validate=[lambda x: x, lambda y: y])
  AttributeField(name)
  >>> fs.name.validators  #doctest: +ELLIPSIS
  [<function <lambda> at ...>, <function <lambda> at ...>, <function <lambda> at ...>, <function <lambda> at ...>]

  >>> fs.name.set(validate='crash')
  Traceback (most recent call last):
  ...
  ValueError: set(validate=...) must be called with either a callable or a list/tuple


Test setting special ones:

  >>> fs.name.validators = []

  >>> fs.name.set(required=True)
  AttributeField(name)
  >>> fs.name.is_required()
  True
  >>> fs.name.validators  #doctest: +ELLIPSIS
  [<function required at ...>]

Shouldn't add it again (')

  >>> fs.name.set(required=True)
  AttributeField(name)
  >>> fs.name.is_required()
  True
  >>> fs.name.validators  #doctest: +ELLIPSIS
  [<function required at ...>]

Should remove the required validator from validators.

  >>> fs.name.set(required=False)
  AttributeField(name)
  >>> fs.name.is_required()
  False
  >>> fs.name.validators
  []

Shouldn't crash, even if it's not there anymore.

  >>> fs.name.set(required=False)
  AttributeField(name)
  >>> fs.name.validators
  []

# Test with a standard/best way to create a FieldSet (custom Class, function that generates a FieldSet ?)
# Test global_validators, being passed to configure() or remove it
  # take from my changeset that fixed configure(), there were some good things
  # in there anyway.
# Test focus on configure(), readonly with previous settings (set in __init__ ?)

# Remove with_metadata (superseded by set()/get())
# Change with_html to html()
# Renderers should say for themselves which settings they're going to use '
#   and those settings can have different meanings for different renderers.
# These should be well documented in each Renderer's __doc__ ... '
# Document (in examples) how to create stacks, with custom settings
#   Example of how to use set(help=u"blah") and show it in the template


# Test .value_objects
#   - Re-test in my app instead, wouldn't raw_value do the same ? '

"""

if __name__ == '__main__':
    import doctest
    doctest.testmod()
