import datetime
import unittest
from nose.tools import *  # flake8: noqa
from website.util import sanitize


class TestSanitize(unittest.TestCase):
    def test_escape_html(self):
        assert_equal(
            sanitize.clean_tag('<script> evil code </script>'),
            '&lt;script&gt; evil code &lt;/script&gt;',
        )
        assert_equal(
            sanitize.clean_tag('<img src=javascript:moreevil><img>'),
            '&lt;img src=&quot;javascript:moreevil&quot;&gt;&lt;img&gt;',
        )
        assert_equal(
            sanitize.clean_tag('<iframe src=evilsite>'),
            '&lt;iframe src=&quot;evilsite&quot;&gt;',
        )
        assert_equal(
            sanitize.clean_tag(');</span><script></script><span>'),
            ');&lt;/span&gt;&lt;script&gt;&lt;/script&gt;&lt;span&gt;',
        )

    def test_clean_tag(self):
        assert_equal(
            sanitize.clean_tag('\'\'\'\'\'"""""""<script></script>'),
            '&#39&#39&#39&#39&#39&quot;&quot;&quot;&quot;&quot;&quot;&quot;&lt;script&gt;&lt;/script&gt;',
        )

    def test_strip_html(self):
        assert_equal(
            sanitize.strip_html('<foo>bar</foo>'),
            'bar'
        )
        assert_equal(
            sanitize.strip_html(b'<foo>bar</foo>'),
            'bar'
        )

    def test_strip_html_on_non_strings_returns_original_value(self):
        assert_true(sanitize.strip_html(True))
        assert_false(sanitize.strip_html(False))

        assert_equal(sanitize.strip_html(12), 12)
        assert_equal(sanitize.strip_html(12.3), 12.3)

        dtime = datetime.datetime.now()
        assert_equal(sanitize.strip_html(dtime), dtime)

    def test_strip_html_sanitizes_collection_types_as_strings(self):
        assert_equal(sanitize.strip_html({'foo': '<b>bar</b>'}), "{'foo': 'bar'}")
        assert_equal(sanitize.strip_html(['<em>baz</em>']), "['baz']")

    def test_unescape_html(self):
        assert_equal(
            sanitize.unescape_entities('&lt;&gt; diamonds &amp; diamonds &lt;&gt;'),
            '&lt;&gt; diamonds & diamonds &lt;&gt;'
        )
        assert_equal(
            sanitize.unescape_entities(['&lt;&gt;&amp;'])[0],
            '&lt;&gt;&'
        )
        assert_equal(
            sanitize.unescape_entities(('&lt;&gt;&amp;', ))[0],
            '&lt;&gt;&'
        )
        assert_equal(
            sanitize.unescape_entities({'key': '&lt;&gt;&amp;'})['key'],
            '&lt;&gt;&'
        )

    def test_safe_json(self):
        """Add escaping of forward slashes, but only where string literal contains closing markup"""
        assert_equal(
            sanitize.safe_json("I'm a string with / containing </closingtags>"),
                               '"I\'m a string with / containing <\\/closingtags>"'
        )
