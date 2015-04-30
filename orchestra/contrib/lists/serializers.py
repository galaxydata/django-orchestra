from django.core.validators import RegexValidator
from django.forms import widgets
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from orchestra.api.serializers import SetPasswordHyperlinkedSerializer
from orchestra.contrib.accounts.serializers import AccountSerializerMixin
from orchestra.core.validators import validate_password

from .models import List


class RelatedDomainSerializer(AccountSerializerMixin, serializers.HyperlinkedModelSerializer):
    class Meta:
        model = List.address_domain.field.rel.to
        fields = ('url', 'id', 'name')
    
    def from_native(self, data, files=None):
        queryset = self.opts.model.objects.filter(account=self.account)
        return get_object_or_404(queryset, name=data['name'])


class ListSerializer(AccountSerializerMixin, SetPasswordHyperlinkedSerializer):
    password = serializers.CharField(max_length=128, label=_('Password'),
        write_only=True, style={'widget': widgets.PasswordInput},
        validators=[
            validate_password,
            RegexValidator(r'^[^"\'\\]+$',
                           _('Enter a valid password. '
                             'This value may contain any ascii character except for '
                             ' \'/"/\\/ characters.'), 'invalid'),
        ])
    
    address_domain = RelatedDomainSerializer(required=False)
    
    class Meta:
        model = List
        fields = ('url', 'id', 'name', 'password', 'address_name', 'address_domain', 'admin_email')
        postonly_fields = ('name', 'password')
    
    def validate_address_domain(self, attrs, source):
        address_domain = attrs.get(source)
        address_name = attrs.get('address_name')
        if self.instance:
            address_domain = address_domain or self.instance.address_domain
            address_name = address_name or self.instance.address_name
        if address_name and not address_domain:
            raise serializers.ValidationError(
                _("address_domains should should be provided when providing an addres_name"))
        return attrs
