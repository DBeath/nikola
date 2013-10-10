# -*- coding: utf-8 -*-

# Copyright © 2012-2013 Roberto Alsina and others.

# Permission is hereby granted, free of charge, to any
# person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice
# shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import unicode_literals, print_function
import os
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin  # NOQA

from nikola import utils
from nikola.utils import makedirs
from nikola.plugin_categories import Task

import PyRSS2Gen as rss

import pytz
import datetime
import codecs
import sys

try:
    from imp import reload
except ImportError:
    pass

if sys.version_info[0] == 3:
    # Python 3
    bytes_str = bytes
    unicode_str = str
    unichr = chr
    from imp import reload as _reload
else:
    bytes_str = str
    unicode_str = unicode  # NOQA
    _reload = reload  # NOQA
    unichr = unichr

class RenderRSS(Task):
    """Generate RSS feeds."""

    name = "render_rss"

    def gen_tasks(self):
        """Generate RSS feeds."""
        kw = {
            "translations": self.site.config["TRANSLATIONS"],
            "filters": self.site.config["FILTERS"],
            "blog_title": self.site.config["BLOG_TITLE"],
            "site_url": self.site.config["SITE_URL"],
            "blog_description": self.site.config["BLOG_DESCRIPTION"],
            "output_folder": self.site.config["OUTPUT_FOLDER"],
            "rss_teasers": self.site.config["RSS_TEASERS"],
            "hide_untranslated_posts": self.site.config['HIDE_UNTRANSLATED_POSTS'],
            "feed_length": self.site.config['FEED_LENGTH'],
        }
        self.site.scan_posts()
        yield self.group_task()
        for lang in kw["translations"]:
            output_name = os.path.join(kw['output_folder'],
                                       self.site.path("rss", None, lang))
            deps = []
            if kw["hide_untranslated_posts"]:
                posts = [x for x in self.site.timeline if x.use_in_feeds
                         and x.is_translation_available(lang)][:10]
            else:
                posts = [x for x in self.site.timeline if x.use_in_feeds][:10]
            for post in posts:
                deps += post.deps(lang)

            feed_url = urljoin(self.site.config['BASE_URL'], self.site.link("rss", None, lang).lstrip('/'))
            yield {
                'basename': 'render_rss',
                'name': os.path.normpath(output_name),
                'file_dep': deps,
                'targets': [output_name],
                'actions': [(generic_rss_renderer,
                            (lang, kw["blog_title"], kw["site_url"],
                             kw["blog_description"], posts, output_name,
                             kw["rss_teasers"], kw['feed_length'], feed_url))],
                'task_dep': ['render_posts'],
                'clean': True,
                'uptodate': [utils.config_changed(kw)],
            }

def generic_rss_renderer(lang, title, link, description, timeline, output_path,
                     rss_teasers, feed_length=10, feed_url=None):
    """Takes all necessary data, and renders a RSS feed in output_path."""
    items = []
    for post in timeline[:feed_length]:
        args = {
            'title': post.title(lang),
            'link': post.permalink(lang, absolute=True),
            'description': post.text(lang, teaser_only=rss_teasers, really_absolute=True),
            'guid': post.permalink(lang, absolute=True),
            # PyRSS2Gen's pubDate is GMT time.
            'pubDate': (post.date if post.date.tzinfo is None else
                        post.date.astimezone(pytz.timezone('UTC'))),
            'categories': post._tags.get(lang, []),
        }
        if post.meta('author') is not None:
            args['author'] = post.meta('author')
        items.append(rss.RSSItem(**args))
    rss_obj = ExtendedRSS2(
        title=title,
        link=link,
        description=description,
        lastBuildDate=datetime.datetime.now(),
        items=items,
        generator='nikola',
        language=lang
    )
    rss_obj.self_url = feed_url
    rss_obj.rss_attrs["xmlns:atom"] = "http://www.w3.org/2005/Atom"
    dst_dir = os.path.dirname(output_path)
    makedirs(dst_dir)
    with codecs.open(output_path, "wb+", "utf-8") as rss_file:
        data = rss_obj.to_xml(encoding='utf-8')
        if isinstance(data, bytes_str):
            data = data.decode('utf-8')
        rss_file.write(data)


class ExtendedRSS2(rss.RSS2):
    def publish_extensions(self, handler):
        if self.self_url:
            handler.startElement("atom:link", {
                'href': self.self_url,
                'rel': "self",
                'type': "application/rss+xml"
            })
            handler.endElement("atom:link")
