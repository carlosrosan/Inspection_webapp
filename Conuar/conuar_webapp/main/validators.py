from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CustomPasswordValidator:
    """
    Custom password validator that enforces:
    - Minimum 10 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character from .!#%$
    """
    
    def __init__(self, min_length=10):
        self.min_length = min_length
        self.special_chars = '.!#%$'
    
    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                _("This password must contain at least %(min_length)d characters."),
                code='password_too_short',
                params={'min_length': self.min_length},
            )
        
        if not any(c.isupper() for c in password):
            raise ValidationError(
                _("This password must contain at least one uppercase letter."),
                code='password_no_upper',
            )
        
        if not any(c.islower() for c in password):
            raise ValidationError(
                _("This password must contain at least one lowercase letter."),
                code='password_no_lower',
            )
        
        if not any(c.isdigit() for c in password):
            raise ValidationError(
                _("This password must contain at least one number."),
                code='password_no_number',
            )
        
        if not any(c in self.special_chars for c in password):
            raise ValidationError(
                _("This password must contain at least one special character from: %(special_chars)s"),
                code='password_no_special',
                params={'special_chars': self.special_chars},
            )
    
    def get_help_text(self):
        return _(
            "Your password must contain at least %(min_length)d characters, "
            "including uppercase letters, lowercase letters, numbers, and "
            "special characters from: %(special_chars)s"
        ) % {'min_length': self.min_length, 'special_chars': self.special_chars}
