__doc__ = r"""
>>> from formalchemy.tests import *

Test validators (most of the other validators are tested somewhere else, this
is where they should get at the end):

  >>> from formalchemy.validators import *
  >>> from formalchemy.fields import Field

passwords_match:

  >>> fs = UserFieldSet()
  >>> post_data = [('User--passwd1', u'pass1'), ('User--passwd2', u'pass2'),
  ...              ('User--name', u'blah'), ('User--email', u'bla@example.com')]
  >>> fs = UserFieldSet().bind(User, data=post_data or None)
  >>> fs.validate()
  False
  >>> fs.errors
  {AttributeField(passwd2): ['Passwords must match']}
  >>>
  >>> post_data = [('User--passwd1', u''), ('User--passwd2', u'pass'),
  ...              ('User--name', u'blah'), ('User--email', u'bla@example.com')]
  >>> fs.rebind(data=post_data)
  >>> fs.validate()
  False
  >>>
  >>> post_data = [('User--passwd1', u'pass'), ('User--passwd2', u'pass'),
  ...              ('User--name', u'blah'), ('User--email', u'bla@example.com')]
  >>> fs.rebind(data=post_data)
  >>> fs.validate()
  True
  >>> fs.errors
  {}

"""


if __name__ == '__main__':
    import doctest
    doctest.testmod()
