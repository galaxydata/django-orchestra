import logging
import os
import re

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from orchestra.core.validators import validate_hostname
from orchestra.utils import paths
from orchestra.utils.sys import run

from .. import domains


logger = logging.getLogger(__name__)


def validate_allowed_domain(value):
    context = {
        'site_dir': paths.get_site_dir()
    }
    fname = domains.settings.DOMAINS_FORBIDDEN
    if fname:
        fname = fname % context
        with open(fname, 'r') as forbidden:
            for domain in forbidden.readlines():
                if re.match(r'^(.*\.)*%s$' % domain.strip(), value):
                    raise ValidationError(_("This domain name is not allowed"))


def validate_domain_name(value):
    # SRV records may use '_' in the domain name
    value = value.lstrip('*.').replace('_', '')
    try:
        validate_hostname(value)
    except ValidationError:
        raise ValidationError(_("Not a valid domain name."))


def validate_zone_interval(value):
    try:
        int(value)
    except ValueError:
        value, magnitude = value[:-1], value[-1]
        if magnitude not in ('s', 'm', 'h', 'd', 'w') or not value.isdigit():
            msg = _("%s is not an appropiate zone interval value") % value
            raise ValidationError(msg)


def validate_zone_label(value):
    """
    http://www.ietf.org/rfc/rfc1035.txt
    The labels must follow the rules for ARPANET host names. They must
    start with a letter, end with a letter or digit, and have as interior
    characters only letters, digits, and hyphen. There are also some
    restrictions on the length. Labels must be 63 characters or less.
    """
    if not re.match(r'^[a-z][\.\-0-9a-z]*[\.0-9a-z]$', value):
        msg = _("Labels must start with a letter, end with a letter or digit, "
                "and have as interior characters only letters, digits, and hyphen")
        raise ValidationError(msg)
    if not value.endswith('.'):
        msg = _("Use a fully expanded domain name ending with a dot")
        raise ValidationError(msg)
    if len(value) > 63:
        raise ValidationError(_("Labels must be 63 characters or less"))


def validate_mx_record(value):
    msg = _("%s is not an appropiate MX record value") % value
    value = value.split()
    if len(value) == 1:
        value = value[0]
    elif len(value) == 2:
        try:
            int(value[0])
        except ValueError:
            raise ValidationError(msg)
        value = value[1]
    elif len(value) > 2:
        raise ValidationError(msg)
    validate_zone_label(value)


def validate_srv_record(value):
    # 1 0 9 server.example.com.
    msg = _("%s is not an appropiate SRV record value") % value
    value = value.split()
    for i in [0,1,2]:
        try:
            int(value[i])
        except ValueError:
            raise ValidationError(msg)
    validate_zone_label(value[-1])


def validate_soa_record(value):
    # ns1.pangea.ORG. hostmaster.pangea.ORG. 2012010401 28800 7200 604800 86400
    msg = _("%s is not an appropiate SRV record value") % value
    values = value.split()
    if len(values) != 7:
        raise ValidationError(msg)
    validate_zone_label(values[0])
    validate_zone_label(values[1])
    for value in values[2:]:
        try:
            int(value)
        except ValueError:
            raise ValidationError(msg)


def validate_zone(zone):
    """ Ultimate zone file validation using named-checkzone """
    zone_name = zone.split()[0][:-1]
    zone_path = os.path.join(domains.settings.DOMAINS_ZONE_VALIDATION_TMP_DIR, zone_name)
    checkzone = domains.settings.DOMAINS_CHECKZONE_BIN_PATH
    try:
        with open(zone_path, 'wb') as f:
            f.write(zone.encode('ascii'))
        # Don't use /dev/stdin becuase the 'argument list is too long' error
        check = run(' '.join([checkzone, zone_name, zone_path]), valid_codes=(0,1,127), display=False)
    finally:
        os.unlink(zone_path)
    if check.exit_code == 127:
        logger.error("Cannot validate domain zone: %s not installed." % checkzone)
    elif check.exit_code == 1:
        errors = re.compile(r'zone.*: (.*)').findall(check.stdout)[:-1]
        raise ValidationError(', '.join(errors))
