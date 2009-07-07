# Copyright (C) 2007 Alexandre Conrad, alexandre (dot) conrad (at) gmail (dot) com
#
# This module is part of FormAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

from formalchemy.i18n import _

__all__ = ['ValidationError', 'required', 'integer', 'float_', 'decimal_',
           'currency', 'email', 'email_verbose', 'maxlength', 'minlength',
           'regex', 'passwords_match']

if 'any' not in locals():
    # pre-2.5 support
    def any(seq):
        """
        >>> any(xrange(10))
        True
        >>> any([0, 0, 0])
        False
        """
        for o in seq:
            if o:
                return True
        return False

class ValidationError(Exception):
    """an exception raised when the validation failed
    """
    def message(self):
        return self.args[0]
    message = property(message)
    def __repr__(self):
        return 'ValidationError(%r,)' % self.message

def required(value, field=None):
    """Successful if value is neither None nor the empty string (yes, including empty lists)"""
    if value is None or value == '':
        msg = isinstance(value, list) and _('Please select a value') or _('Please enter a value')
        raise ValidationError(msg)

# other validators will not be called for empty values

def integer(value, field=None):
    """Successful if value is an int"""
    # the validator contract says you don't have to worry about "value is None",
    # but this is called from deserialize as well as validation
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except:
        raise ValidationError(_('Value is not an integer'))

def float_(value, field=None):
    """Successful if value is a float"""
    # the validator contract says you don't have to worry about "value is None",
    # but this is called from deserialize as well as validation
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except:
        raise ValidationError(_('Value is not a number'))

from decimal import Decimal
def decimal_(value, field=None):
    """Successful if value can represent a decimal"""
    # the validator contract says you don't have to worry about "value is None",
    # but this is called from deserialize as well as validation
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value)
    except:
        raise ValidationError(_('Value is not a number'))

def currency(value, field=None):
    """Successful if value looks like a currency amount (has exactly two digits after a decimal point)"""
    if '%.2f' % float_(value) != value:
        raise ValidationError('Please specify full currency value, including cents (e.g., 12.34)')

def email_verbose(value, field=None):
    """
    Successful if value is a valid RFC 822 email address.
    Ignores the more subtle intricacies of what is legal inside a quoted region,
    and thus may accept some
    technically invalid addresses, but will never reject a valid address
    (which is a much worse problem).
    """
    if not value.strip():
        return None

    reserved = r'()<>@,;:\"[]'

    try:
        recipient, domain = value.split('@', 1)
    except ValueError:
        raise ValidationError(_('Missing @ sign'))

    if any([ord(ch) < 32 for ch in value]):
        raise ValidationError(_('Control characters present'))
    if any([ord(ch) > 127 for ch in value]):
        raise ValidationError(_('Non-ASCII characters present'))

    # validate recipient
    if not recipient:
        raise ValidationError(_('Recipient must be non-empty'))
    if recipient.endswith('.'):
        raise ValidationError(_("Recipient must not end with '.'"))

    # quoted regions, aka the reason any regexp-based validator is wrong
    i = 0
    while i < len(recipient):
        if recipient[i] == '"' and (i == 0 or recipient[i - 1] == '.' or recipient[i - 1] == '"'):
            # begin quoted region -- reserved characters are allowed here.
            # (this implementation allows a few addresses not strictly allowed by rfc 822 --
            # for instance, a quoted region that ends with '\' appears to be illegal.)
            i += 1
            while i < len(recipient):
                if recipient[i] == '"':
                    break # end of quoted region
                i += 1
            else:
                raise ValidationError(_("Unterminated quoted section in recipient"))
            i += 1
            if i < len(recipient) and recipient[i] != '.':
                raise ValidationError(_("Quoted section must be followed by '@' or '.'"))
            continue
        if recipient[i] in reserved:
            raise ValidationError(_("Reserved character present in recipient"))
        i += 1

    # validate domain
    if not domain:
        raise ValidationError(_('Domain must be non-empty'))
    if domain.endswith('.'):
        raise ValidationError(_("Domain must not end with '.'"))
    if '..' in domain:
        raise ValidationError(_("Domain must not contain '..'"))
    if any([ch in reserved for ch in domain]):
        raise ValidationError(_("Reserved character present in domain"))


def email(value, field=None):
    """Defines a less verbose and explicit error message when validation
    fails"""
    try:
        email_verbose(value, field)
    except ValidationError:
        raise ValidationError(_("Invalid e-mail address"))


# parameterized validators return the validation function
def maxlength(length):
    """Returns a validator that is successful if the input's length is at most the given one."""
    if length <= 0:
        raise ValueError('Invalid maximum length')
    def f(value, field=None):
        if len(value) > length:
            raise ValidationError(_('Value must be no more than %d characters long') % length)
    return f

def minlength(length):
    """Returns a validator that is successful if the input's length is at least the given one."""
    if length <= 0:
        raise ValueError('Invalid minimum length')
    def f(value, field=None):
        if len(value) < length:
            raise ValidationError(_('Value must be at least %d characters long') % length)
    return f

def regex(exp, errormsg=_('Invalid input')):
    """
    Returns a validator that is successful if the input matches (that is,
    fulfils the semantics of re.match) the given expression.
    Expressions may be either a string or a Pattern object of the sort returned by
    re.compile.
    """
    import re
    if type(exp) != type(re.compile('')):
        exp = re.compile(exp)
    def f(value, field=None):
        if not exp.match(value):
            raise ValidationError(errormsg)
    return f

def passwords_match(first_password_field):
    """This validator ensures two password fields match.

    You can provide either a Field objet, or a string with the
    name of the field on the FieldSet that will be checked
    against to make sure they match. That means you should set
    this validator on the `second` password field.

    NOTE: this validator must be attached to a Field that is
    itself on a FieldSet.
    """
    def f(value, field):
        if isinstance(first_password_field, (str, unicode)):
            fld = first_password_field
        else:
            fld = first_password_field.key

        if value != getattr(field.parent, fld).value:
            raise ValidationError(_('Passwords must match'))
    return f

# possible others:
# oneof raises if input is not one of [or a subset of for multivalues] the given list of possibilities
# url(check_exists=False)
# address parts
# cidr
# creditcard number/securitycode (/expires?)
# whole-form validators
#   fieldsmatch
#   requiredipresent/missing
