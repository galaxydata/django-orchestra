import datetime
import inspect
from functools import wraps

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db import models
from django.shortcuts import redirect
import importlib
from django.utils.html import escape
from django.utils.safestring import mark_safe

from orchestra.models.utils import get_field_value
from orchestra.utils import humanize

from .decorators import admin_field
from .html import monospace_format


def get_modeladmin(model, import_module=True):
    """ returns the modeladmin registred for model """
    for k,v in admin.site._registry.items():
        if k is model:
            return v
    if import_module:
        # Sometimes the admin module is not yet imported
        app_label = model._meta.app_label
        for app in settings.INSTALLED_APPS:
            if app.endswith(app_label):
                app_label = app
        importlib.import_module('%s.%s' % (app_label, 'admin'))
        return get_modeladmin(model, import_module=False)


def insertattr(model, name, value):
    """ Inserts attribute to a modeladmin """
    modeladmin = None
    if issubclass(model, models.Model):
        modeladmin = get_modeladmin(model)
        modeladmin_class = type(modeladmin)
    elif not inspect.isclass(model):
        modeladmin = model
        modeladmin_class = type(modeladmin)
    else:
        modeladmin_class = model
    # Avoid inlines defined on parent class be shared between subclasses
    # Seems that if we use tuples they are lost in some conditions like changing
    # the tuple in modeladmin.__init__
    if not getattr(modeladmin_class, name):
        setattr(modeladmin_class, name, [])
    setattr(modeladmin_class, name, list(getattr(modeladmin_class, name))+[value])
    if modeladmin:
        # make sure class and object share the same attribute, to avoid wierd bugs
        setattr(modeladmin, name, getattr(modeladmin_class, name))


def wrap_admin_view(modeladmin, view):
    """ Add admin authentication to view """
    @wraps(view)
    def wrapper(*args, **kwargs):
        return modeladmin.admin_site.admin_view(view)(*args, **kwargs)
    return wrapper


def set_url_query(request, key, value):
    """ set default filters for changelist_view """
    if key not in request.GET:
        request_copy = request.GET.copy()
        if callable(value):
            value = value(request)
        request_copy[key] = value
        request.GET = request_copy
        request.META['QUERY_STRING'] = request.GET.urlencode()


def action_to_view(action, modeladmin):
    """ Converts modeladmin action to view function """
    @wraps(action)
    def action_view(request, object_id=1, modeladmin=modeladmin, action=action):
        queryset = modeladmin.model.objects.filter(pk=object_id)
        response = action(modeladmin, request, queryset)
        if not response:
            opts = modeladmin.model._meta
            url = 'admin:%s_%s_change' % (opts.app_label, opts.model_name)
            return redirect(url, object_id)
        return response
    return action_view


def change_url(obj):
    opts = obj._meta
    view_name = 'admin:%s_%s_change' % (opts.app_label, opts.model_name)
    return reverse(view_name, args=(obj.pk,))


@admin_field
def admin_link(*args, **kwargs):
    instance = args[-1]
    if kwargs['field'] in ['id', 'pk', '__str__']:
        obj = instance
    else:
        try:
            obj = get_field_value(instance, kwargs['field'])
        except ObjectDoesNotExist:
            return '---'
    if not getattr(obj, 'pk', None):
        return '---'
    url = change_url(obj)
    display = kwargs.get('display')
    if display:
        display = getattr(obj, display, 'merda')
    else:
        display = obj
    extra = ''
    if kwargs['popup']:
        extra = 'onclick="return showAddAnotherPopup(this);"'
    return '<a href="%s" %s>%s</a>' % (url, extra, display)


@admin_field
def admin_colored(*args, **kwargs):
    instance = args[-1]
    field = kwargs['field']
    value = escape(get_field_value(instance, field))
    color = kwargs.get('colors', {}).get(value, 'black')
    value = getattr(instance, 'get_%s_display' % field)().upper()
    colored_value = '<span style="color: %s;">%s</span>' % (color, value)
    if kwargs.get('bold', True):
        colored_value = '<b>%s</b>' % colored_value
    return mark_safe(colored_value)


@admin_field
def admin_date(*args, **kwargs):
    instance = args[-1]
    value = get_field_value(instance, kwargs['field'])
    if not value:
        return kwargs.get('default', '')
    if isinstance(value, datetime.datetime):
        natural = humanize.naturaldatetime(value)
    else:
        natural = humanize.naturaldate(value)
    return '<span title="{0}">{1}</span>'.format(
        escape(str(value)), escape(natural),
    )


def get_object_from_url(modeladmin, request):
    try:
        object_id = int(request.path.split('/')[-3])
    except ValueError:
        return None
    else:
        return modeladmin.model.objects.get(pk=object_id)


def display_mono(field):
    def display(self, log):
        return monospace_format(escape(getattr(log, field)))
    display.short_description = field
    return display
