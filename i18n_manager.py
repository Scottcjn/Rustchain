// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import os
from flask import request, session


class I18nManager:
    def __init__(self, app=None, default_locale='en'):
        self.default_locale = default_locale
        self.locale = default_locale
        self.translations = {}
        self.i18n_dir = 'i18n'
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
        if not os.path.exists(self.i18n_dir):
            os.makedirs(self.i18n_dir)
        self.load_translations()
        
        @app.before_request
        def before_request():
            self.locale = self.get_locale()
    
    def load_translations(self):
        for filename in os.listdir(self.i18n_dir):
            if filename.endswith('.json'):
                lang_code = filename[:-5]
                try:
                    with open(os.path.join(self.i18n_dir, filename), 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                except (json.JSONDecodeError, IOError):
                    continue
    
    def get_locale(self):
        if 'locale' in session:
            return session['locale']
        
        if request and request.args.get('lang'):
            return request.args.get('lang')
        
        if request and request.headers.get('Accept-Language'):
            accept_lang = request.headers.get('Accept-Language')
            preferred = accept_lang.split(',')[0].split('-')[0]
            if preferred in self.translations:
                return preferred
        
        return self.default_locale
    
    def set_locale(self, locale):
        if locale in self.translations:
            session['locale'] = locale
            self.locale = locale
    
    def gettext(self, message, **kwargs):
        if self.locale in self.translations:
            translated = self.translations[self.locale].get(message, message)
        else:
            translated = message
        
        if kwargs:
            try:
                return translated.format(**kwargs)
            except (KeyError, ValueError):
                return translated
        
        return translated
    
    def ngettext(self, singular, plural, count):
        message = singular if count == 1 else plural
        return self.gettext(message, count=count)
    
    def get_available_locales(self):
        return list(self.translations.keys())


i18n = I18nManager()

def gettext(message, **kwargs):
    return i18n.gettext(message, **kwargs)

def ngettext(singular, plural, count):
    return i18n.ngettext(singular, plural, count)

def lazy_gettext(message, **kwargs):
    def deferred():
        return gettext(message, **kwargs)
    return deferred