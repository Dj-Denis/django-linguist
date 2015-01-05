# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django
from django.conf.urls import patterns, url
from django.contrib import admin
from django.contrib.admin.options import csrf_protect_m
from django.contrib.admin.util import unquote
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.core.urlresolvers import reverse
from django.forms import Media
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render
from django.utils.encoding import iri_to_uri, force_text
from django.utils.functional import lazy
from django.utils.http import urlencode
from django.utils.translation import ugettext_lazy as _
from django.utils import six

from . import utils

from .forms import ModelTranslationForm
from .models import Translation as LinguistTranslationModel

__all__ = [
    'ModelTranslationAdmin',
]


_lazy_select_template_name = lazy(utils.select_template_name, six.text_type)


class ModelTranslationAdmin(admin.ModelAdmin):

    def get_available_languages(self, obj):
        """
        Returns available languages for current object.
        """
        return obj.available_languages if obj is not None else self.model.objects.none()

    def languages_column(self, obj):
        """
        Adds languages columns.
        """
        languages = self.get_available_languages(obj)
        return '<span class="available-languages">{0}</span>'.format(' '.join(languages))

    languages_column.allow_tags = True
    languages_column.short_description = _('Languages')


class ModelTranslationTabbedAdmin(admin.ModelAdmin):

    form = ModelTranslationForm
    query_language_key = 'language'

    @property
    def media(self):
        """
        Add Linguist media files.
        """
        return super(ModelTranslationAdmin, self).media + Media(css={
          'all': ('linguist/admin/language_tabs.css',)})

    def get_language(self, request):
        """
        Returns current language (from request).
        """
        return utils.get_language_parameter(request, self.query_language_key)

    def get_language_tabs(self, request, obj, available_languages, css_class=None):
        """
        Returns language tabs.
        """
        current_language = self.get_language(request)
        return utils.get_language_tabs(
            request,
            current_language,
            available_languages,
            css_class=css_class)

    @property
    def change_form_template(self):
        """
        Overrides ``admin/change_form.html`` template.
        """
        return 'admin/linguist/change_form.html'

    def get_change_form_base_template(self):
        """
        Overrides base change form template.
        """
        opts = self.model._meta
        app_label = opts.app_label
        return _lazy_select_template_name((
            "admin/{0}/{1}/change_form.html".format(app_label, opts.object_name.lower()),
            "admin/{0}/change_form.html".format(app_label),
            "admin/change_form.html"))

    def get_available_languages(self, obj):
        """
        Returns available languages for current object.
        """
        return obj.available_languages if obj is not None else self.model.objects.none()

    def languages_column(self, obj):
        """
        Adds languages columns.
        """
        languages = self.get_available_languages(obj)
        return '<span class="available-languages">{0}</span>'.format(' '.join(languages))

    languages_column.allow_tags = True
    languages_column.short_description = _('Languages')

    def get_object(self, request, object_id):
        """
        Returns current object.
        """
        obj = super(ModelTranslationAdmin, self).get_object(request, object_id)
        if obj is not None:
            obj.language = self.get_language(request)
        return obj

    def get_form_language(self, request):
        """
        Returns the current language for the currently displayed object fields.
        """
        return self.get_language(request)

    def get_form(self, request, obj=None, **kwargs):
        """
        Passes the current language to the form.
        """
        form_class = super(ModelTranslationAdmin, self).get_form(request, obj, **kwargs)
        form_class.language = self.get_form_language(request)
        return form_class

    def get_urls(self):
        """
        Overrides URLs to add delete translations URLs.
        """
        urlpatterns = super(ModelTranslationAdmin, self).get_urls()
        opts = self.model._meta
        info = opts.app_label, opts.model_name if django.VERSION >= (1, 7) else opts.module_name
        return patterns('',
            url(r'^(.+)/delete-translation/(.+)/$',
                self.admin_site.admin_view(self.delete_translations),
                name='{0}_{1}_delete_translation'.format(*info)
            ),
        ) + urlpatterns

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        """
        Renders change form.
        """
        language = self.get_language(request)
        available_languages = self.get_available_languages(obj)
        language_tabs = self.get_language_tabs(request, obj, available_languages)
        context['language_tabs'] = language_tabs

        if language_tabs:
            context['title'] = '%s (%s)' % (context['title'], language)

        if not language_tabs.current_is_translated:
            add = True

        form_url = add_preserved_filters({
            'preserved_filters': urlencode({'language': language}),
            'opts': self.model._meta
        }, form_url)

        if 'default_change_form_template' not in context:
            context['default_change_form_template'] = self.get_change_form_base_template()

        return super(ModelTranslationAdmin, self).render_change_form(request, context, add, change, form_url, obj)

    def response_add(self, request, obj, post_url_continue=None):
        """
        Handles rediret at response add.
        """
        redirect = super(ModelTranslationAdmin, self).response_add(request, obj, post_url_continue)
        return self._patch_redirect(request, obj, redirect)

    def response_change(self, request, obj):
        """
        Handes redirect at response change.
        """
        redirect = super(ModelTranslationAdmin, self).response_change(request, obj)
        return self._patch_redirect(request, obj, redirect)

    def _patch_redirect(self, request, obj, redirect):
        """
        Redirects to the relavant language.
        """
        if redirect.status_code not in (301, 302):
            return redirect
        uri = iri_to_uri(request.path)
        opts = self.model._meta
        info = (opts.app_label, opts.model_name if django.VERSION >= (1, 7) else opts.module_name)
        language = request.GET.get(self.query_language_key)
        if language:
            continue_urls = (uri, "../add/", reverse('admin:{0}_{1}_add'.format(*info)))
            if redirect['Location'] in continue_urls and self.query_language_key in request.GET:
                redirect['Location'] += "?{0}={1}".format(self.query_language_key, language)
        return redirect

    @csrf_protect_m
    def delete_translations(self, request, object_id, language):
        """
        Deletes object related translations.
        """
        opts = self.model._meta
        obj = self.get_object(request, unquote(object_id))
        language_name = utils.get_language_name(language)

        if obj is None:
            raise Http404

        deleted_objects = [
            '%(name)s - %(language)s - %(field_name)s' % dict(
                name=force_text(opts.verbose_name),
                language=language_name,
                field_name=trans.field_name)
            for trans in obj.get_translations(language=language)]

        object_name = _('%(language)s translations of %(name)s') % dict(
            language=language_name,
            name=force_text(opts.verbose_name))

        if request.POST:
            obj.delete_translations(language=language)
            self.message_user(
                request,
                _('%(language)s translations of %(name)s was deleted successfully.') % dict(
                    language=language_name,
                    name=force_text(opts.verbose_name)))

            if self.has_change_permission(request, None):
                return HttpResponseRedirect(reverse('admin:{0}_{1}_changelist'.format(
                    opts.app_label,
                    opts.model_name if django.VERSION >= (1, 7) else opts.module_name)))
            else:
                return HttpResponseRedirect(reverse('admin:index'))

        context = {
            "title": _("Are you sure?"),
            "object_name": object_name,
            "object": obj,
            "deleted_objects": deleted_objects,
            "perms_lacking": False,
            "protected": False,
            "opts": opts,
            "app_label": opts.app_label,
        }

        return render(request, self.delete_confirmation_template or [
            "admin/%s/%s/delete_confirmation.html" % (opts.app_label, opts.object_name.lower()),
            "admin/%s/delete_confirmation.html" % opts.app_label,
            "admin/delete_confirmation.html"
        ], context)


class LinguistTranslationModelAdmin(admin.ModelAdmin):
    """
    Linguist Translation admin options.
    """
    list_display = ('identifier', 'object_id', 'language', 'field_name', 'field_value')


admin.site.register(LinguistTranslationModel, LinguistTranslationModelAdmin)
