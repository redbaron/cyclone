#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Translation methods for generating localized strings.

To load a locale and generate a translated string:

    user_locale = locale.get("es_LA")
    print user_locale.translate("Sign out")

locale.get() returns the closest matching locale, not necessarily the
specific locale you requested. You can support pluralization with
additional arguments to translate(), e.g.:

    people = [...]
    message = user_locale.translate(
        "%(list)s is online", "%(list)s are online", len(people))
    print message % {"list": user_locale.list(people)}

The first string is chosen if len(people) == 1, otherwise the second
string is chosen.
"""

try:
    import gettext
except ImportError:
    raise Exception("The gettext module is required, download at "
                    "http://pypi.python.org/pypi/python-gettext")

import os
import os.path
import datetime
from twisted.python import log

_default_locale = "en_US"
_translations = {}
_supported_locales = frozenset([_default_locale])


def get(*locale_codes):
    """Returns the closest match for the given locale codes.

    We iterate over all given locale codes in order. If we have a tight
    or a loose match for the code (e.g., "en" for "en_US"), we return
    the locale. Otherwise we move to the next code in the list.

    By default we return en_US if no translations are found for any of
    the specified locales. You can change the default locale with
    set_default_locale() below.
    """
    return Locale.get_closest(*locale_codes)


def set_default_locale(code):
    """Sets the default locale, used in get_closest_locale().

    The default locale is assumed to be the language used for all strings
    in the system. The translations loaded from disk are mappings from
    the default locale to the destination locale. Consequently, you don't
    need to create a translation file for the default locale.
    """
    global _default_locale
    global _supported_locales
    _default_locale = code
    _supported_locales = frozenset(_translations.keys() + [_default_locale])


def load_translations(directory, domain="cyclone"):
    """Loads translations from gettext's locale tree

    Locale tree is similar to system's /usr/share/locale, like:

    {directory}/{lang}/LC_MESSAGES/{domain}.mo

    Three steps are required to have you app translated:

    1. Generate POT translation file
        xgettext --language=Python --keyword=_:1,2 -d cyclone file1.py file2.html etc

    2. Merge against existing POT file:
        msgmerge old.po cyclone.po > new.po

    3. Compile:
        msgfmt cyclone.po -o {directory}/pt_BR/LC_MESSAGES/cyclone.mo

    """
    global _translations
    global _supported_locales
    _translations = {}

    for lang in os.listdir(directory):
        try:
            os.stat(os.path.join(directory, lang, "LC_MESSAGES", domain+".mo"))
            _translations[lang] = gettext.translation(domain, directory, languages=[lang])
        except Exception, e:
            log.err("Cannot load translation for '%s': %s" % (lang, str(e)))
            continue

    _supported_locales = frozenset(_translations.keys() + [_default_locale])
    log.msg("Supported locales: %s" % sorted(_supported_locales))


def get_supported_locales():
    """Returns a list of all the supported locale codes."""
    return _supported_locales


class Locale(object):
    @classmethod
    def get_closest(cls, *locale_codes):
        """Returns the closest match for the given locale code."""
        for code in locale_codes:
            if not code:
                continue

            code = code.replace("-", "_")
            parts = code.split("_")
            if len(parts) > 2:
                continue
            elif len(parts) == 2:
                code = parts[0].lower() + "_" + parts[1].upper()

            if code in _supported_locales:
                return cls.get(code)

            if parts[0].lower() in _supported_locales:
                return cls.get(parts[0].lower())

        return cls.get(_default_locale)

    @classmethod
    def get(cls, code):
        """Returns the Locale for the given locale code.

        If it is not supported, we raise an exception.
        """
        translator = _translations.get(code, None)
        if translator is None:
            translator = gettext.NullTranslations()
        return Locale(code, translator)

    def __init__(self, code, translator):
        self.code = code
        self.name = LOCALE_NAMES.get(code, {}).get("name", u"Unknown")
        self.rtl = False
        for prefix in ["fa", "ar", "he"]:
            if self.code.startswith(prefix):
                self.rtl = True
                break

        self.translator = translator

        # Initialize strings for date formatting
        _ = self.translate
        self._months = [
            _("January"), _("February"), _("March"), _("April"),
            _("May"), _("June"), _("July"), _("August"), 
            _("September"), _("October"), _("November"), _("December")]
        self._weekdays = [
            _("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"),
            _("Friday"), _("Saturday"), _("Sunday")]

    def translate(self, message, plural_message=None, count=None):
        """Returns the translation for the given message for this locale.

        If plural_message is given, you must also provide count. We return
        plural_message when count != 1, and we return the singular form
        for the given message when count == 1.
        """
        if plural_message is not None:
            if count is not None:
                return self.translator.ngettext(message, plural_message, count)
            else:
                return self.translator.gettext(message)
        else:
            return self.translator.gettext(message)

    def format_date(self, date, gmt_offset=0, relative=True, shorter=False,
                    full_format=False):
        """Formats the given date (which should be GMT).

        By default, we return a relative time (e.g., "2 minutes ago"). You
        can return an absolute date string with relative=False.

        You can force a full format date ("July 10, 1980") with
        full_format=True.
        """
        if self.code.startswith("ru"):
            relative = False
        if type(date) in (int, long, float):
            date = datetime.datetime.utcfromtimestamp(date)
        now = datetime.datetime.utcnow()
        # Round down to now. Due to click skew, things are somethings
        # slightly in the future.
        if date > now:
            date = now
        local_date = date - datetime.timedelta(minutes=gmt_offset)
        local_now = now - datetime.timedelta(minutes=gmt_offset)
        local_yesterday = local_now - datetime.timedelta(hours=24)
        difference = now - date
        seconds = difference.seconds
        days = difference.days

        _ = self.translate
        format = None
        if not full_format:
            if relative and days == 0:
                if seconds < 50:
                    return _("1 second ago", "%(seconds)d seconds ago",
                             seconds) % { "seconds": seconds }

                if seconds < 50 * 60:
                    minutes = round(seconds / 60.0)
                    return _("1 minute ago", "%(minutes)d minutes ago",
                             minutes) % { "minutes": minutes }

                hours = round(seconds / (60.0 * 60))
                return _("1 hour ago", "%(hours)d hours ago",
                         hours) % { "hours": hours }

            if days == 0:
                format = _("%(time)s")
            elif days == 1 and local_date.day == local_yesterday.day and \
                 relative:
                format = _("yesterday") if shorter else \
                         _("yesterday at %(time)s")
            elif days < 5:
                format = _("%(weekday)s") if shorter else \
                         _("%(weekday)s at %(time)s")
            elif days < 334:  # 11mo, since confusing for same month last year
                format = _("%(month_name)s %(day)s") if shorter else \
                         _("%(month_name)s %(day)s at %(time)s")

        if format is None:
            format = _("%(month_name)s %(day)s, %(year)s") if shorter else \
                     _("%(month_name)s %(day)s, %(year)s at %(time)s")

        tfhour_clock = self.code not in ("en", "en_US", "zh_CN")
        if tfhour_clock:
            str_time = "%d:%02d" % (local_date.hour, local_date.minute)
        elif self.code == "zh_CN":
            str_time = "%s%d:%02d" % (
                (u'\u4e0a\u5348', u'\u4e0b\u5348')[local_date.hour >= 12],
                local_date.hour % 12 or 12, local_date.minute)
        else:
            str_time = "%d:%02d %s" % (
                local_date.hour % 12 or 12, local_date.minute,
                ("am", "pm")[local_date.hour >= 12])

        return format % {
            "month_name": self._months[local_date.month - 1],
            "weekday": self._weekdays[local_date.weekday()],
            "day": str(local_date.day),
            "year": str(local_date.year),
            "time": str_time
        }

    def format_day(self, date, gmt_offset=0, dow=True):
        """Formats the given date as a day of week.

        Example: "Monday, January 22". You can remove the day of week with
        dow=False.
        """
        local_date = date - datetime.timedelta(minutes=gmt_offset)
        _ = self.translate
        if dow:
            return _("%(weekday)s, %(month_name)s %(day)s") % {
                "month_name": self._months[local_date.month - 1],
                "weekday": self._weekdays[local_date.weekday()],
                "day": str(local_date.day),
            }
        else:
            return _("%(month_name)s %(day)s") % {
                "month_name": self._months[local_date.month - 1],
                "day": str(local_date.day),
            }

    def list(self, parts):
        """Returns a comma-separated list for the given list of parts.

        The format is, e.g., "A, B and C", "A and B" or just "A" for lists
        of size 1.
        """
        _ = self.translate
        if len(parts) == 0:
            return ""
        if len(parts) == 1:
            return parts[0]
        comma = u' \u0648 ' if self.code.startswith("fa") else u", "
        return _("%(commas)s and %(last)s") % {
            "commas": comma.join(parts[:-1]),
            "last": parts[len(parts) - 1],
        }

    def friendly_number(self, value):
        """Returns a comma-separated number for the given integer."""
        if self.code not in ("en", "en_US"):
            return str(value)
        value = str(value)
        parts = []
        while value:
            parts.append(value[-3:])
            value = value[:-3]
        return ",".join(reversed(parts))


LOCALE_NAMES = {
    "af_ZA": {"name_en": u"Afrikaans", "name": u"Afrikaans"},
    "ar_AR": {"name_en": u"Arabic", "name": u"\u0627\u0644\u0639\u0631\u0628\u064a\u0629"},
    "bg_BG": {"name_en": u"Bulgarian", "name": u"\u0411\u044a\u043b\u0433\u0430\u0440\u0441\u043a\u0438"},
    "bn_IN": {"name_en": u"Bengali", "name": u"\u09ac\u09be\u0982\u09b2\u09be"},
    "bs_BA": {"name_en": u"Bosnian", "name": u"Bosanski"},
    "ca_ES": {"name_en": u"Catalan", "name": u"Catal\xe0"},
    "cs_CZ": {"name_en": u"Czech", "name": u"\u010ce\u0161tina"},
    "cy_GB": {"name_en": u"Welsh", "name": u"Cymraeg"},
    "da_DK": {"name_en": u"Danish", "name": u"Dansk"},
    "de_DE": {"name_en": u"German", "name": u"Deutsch"},
    "el_GR": {"name_en": u"Greek", "name": u"\u0395\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac"},
    "en_GB": {"name_en": u"English (UK)", "name": u"English (UK)"},
    "en_US": {"name_en": u"English (US)", "name": u"English (US)"},
    "es_ES": {"name_en": u"Spanish (Spain)", "name": u"Espa\xf1ol (Espa\xf1a)"},
    "es_LA": {"name_en": u"Spanish", "name": u"Espa\xf1ol"},
    "et_EE": {"name_en": u"Estonian", "name": u"Eesti"},
    "eu_ES": {"name_en": u"Basque", "name": u"Euskara"},
    "fa_IR": {"name_en": u"Persian", "name": u"\u0641\u0627\u0631\u0633\u06cc"},
    "fi_FI": {"name_en": u"Finnish", "name": u"Suomi"},
    "fr_CA": {"name_en": u"French (Canada)", "name": u"Fran\xe7ais (Canada)"},
    "fr_FR": {"name_en": u"French", "name": u"Fran\xe7ais"},
    "ga_IE": {"name_en": u"Irish", "name": u"Gaeilge"},
    "gl_ES": {"name_en": u"Galician", "name": u"Galego"},
    "he_IL": {"name_en": u"Hebrew", "name": u"\u05e2\u05d1\u05e8\u05d9\u05ea"},
    "hi_IN": {"name_en": u"Hindi", "name": u"\u0939\u093f\u0928\u094d\u0926\u0940"},
    "hr_HR": {"name_en": u"Croatian", "name": u"Hrvatski"},
    "hu_HU": {"name_en": u"Hungarian", "name": u"Magyar"},
    "id_ID": {"name_en": u"Indonesian", "name": u"Bahasa Indonesia"},
    "is_IS": {"name_en": u"Icelandic", "name": u"\xcdslenska"},
    "it_IT": {"name_en": u"Italian", "name": u"Italiano"},
    "ja_JP": {"name_en": u"Japanese", "name": u"\xe6\xe6\xe8"},
    "ko_KR": {"name_en": u"Korean", "name": u"\xed\xea\xec"},
    "lt_LT": {"name_en": u"Lithuanian", "name": u"Lietuvi\u0173"},
    "lv_LV": {"name_en": u"Latvian", "name": u"Latvie\u0161u"},
    "mk_MK": {"name_en": u"Macedonian", "name": u"\u041c\u0430\u043a\u0435\u0434\u043e\u043d\u0441\u043a\u0438"},
    "ml_IN": {"name_en": u"Malayalam", "name": u"\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02"},
    "ms_MY": {"name_en": u"Malay", "name": u"Bahasa Melayu"},
    "nb_NO": {"name_en": u"Norwegian (bokmal)", "name": u"Norsk (bokm\xe5l)"},
    "nl_NL": {"name_en": u"Dutch", "name": u"Nederlands"},
    "nn_NO": {"name_en": u"Norwegian (nynorsk)", "name": u"Norsk (nynorsk)"},
    "pa_IN": {"name_en": u"Punjabi", "name": u"\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40"},
    "pl_PL": {"name_en": u"Polish", "name": u"Polski"},
    "pt_BR": {"name_en": u"Portuguese (Brazil)", "name": u"Portugu\xeas (Brasil)"},
    "pt_PT": {"name_en": u"Portuguese (Portugal)", "name": u"Portugu\xeas (Portugal)"},
    "ro_RO": {"name_en": u"Romanian", "name": u"Rom\xe2n\u0103"},
    "ru_RU": {"name_en": u"Russian", "name": u"\u0420\u0443\u0441\u0441\u043a\u0438\u0439"},
    "sk_SK": {"name_en": u"Slovak", "name": u"Sloven\u010dina"},
    "sl_SI": {"name_en": u"Slovenian", "name": u"Sloven\u0161\u010dina"},
    "sq_AL": {"name_en": u"Albanian", "name": u"Shqip"},
    "sr_RS": {"name_en": u"Serbian", "name": u"\u0421\u0440\u043f\u0441\u043a\u0438"},
    "sv_SE": {"name_en": u"Swedish", "name": u"Svenska"},
    "sw_KE": {"name_en": u"Swahili", "name": u"Kiswahili"},
    "ta_IN": {"name_en": u"Tamil", "name": u"\u0ba4\u0bae\u0bbf\u0bb4\u0bcd"},
    "te_IN": {"name_en": u"Telugu", "name": u"\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41"},
    "th_TH": {"name_en": u"Thai", "name": u"\u0e20\u0e32\u0e29\u0e32\u0e44\u0e17\u0e22"},
    "tl_PH": {"name_en": u"Filipino", "name": u"Filipino"},
    "tr_TR": {"name_en": u"Turkish", "name": u"T\xfcrk\xe7e"},
    "uk_UA": {"name_en": u"Ukraini ", "name": u"\u0423\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u0430"},
    "vi_VN": {"name_en": u"Vietnamese", "name": u"Ti\u1ebfng Vi\u1ec7t"},
    "zh_CN": {"name_en": u"Chinese (Simplified)", "name": u"\xe4\xe6(\xe7\xe4)"},
    "zh_HK": {"name_en": u"Chinese (Hong Kong)", "name": u"\xe4\xe6(\xe9\xe6)"},
    "zh_TW": {"name_en": u"Chinese (Taiwan)", "name": u"\xe4\xe6(\xe5\xe7)"},
}
