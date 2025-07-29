# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from core.sanitiers import HtmlEscapeSanitizer, Nh3Sanitizer
from tests.base import TestCase


class TestNh3Sanitizer(TestCase):
    """
    测试 Nh3Sanitizer 的功能，它应该保留安全的HTML，剥离危险的HTML。
    """

    def test_default_options_remove_dangerous_tags(self):
        """
        测试：默认配置应移除 script, iframe 等危险标签。
        """
        sanitizer = Nh3Sanitizer()
        dirty_html = "<p>这是段落。</p><script>alert('XSS');</script><iframe>病毒网站</iframe>"
        clean_html = sanitizer.sanitize(dirty_html)
        self.assertEqual(clean_html, "<p>这是段落。</p>病毒网站")

    def test_default_options_remove_dangerous_attributes(self):
        """
        测试：默认配置应移除 onclick, onmouseover 等危险属性。
        """
        sanitizer = Nh3Sanitizer()
        dirty_html = "<a href='/path' title='提示' onclick='danger()'>链接</a><p onmouseover='danger2()'>文本</p>"
        clean_html = sanitizer.sanitize(dirty_html)
        # 注意：nh3 可能会规范化属性的引号
        self.assertEqual(clean_html, '<a href="/path" title="提示" rel="noopener noreferrer">链接</a><p>文本</p>')

    def test_default_options_clean_dangerous_href(self):
        """
        测试：默认配置应清理 a 标签中危险的 href 值。
        """
        sanitizer = Nh3Sanitizer()
        dirty_html = '<a href="javascript:alert(1)">恶意链接</a>'
        clean_html = sanitizer.sanitize(dirty_html)
        # href 属性被整个移除，因为它的协议是危险的
        self.assertEqual(clean_html, """<a rel="noopener noreferrer">恶意链接</a>""")

    def test_custom_options_are_applied(self):
        """
        测试：可以通过构造函数传入自定义的 nh3 选项。
        """
        # 自定义规则：只允许 <b> 标签，其他全部移除
        custom_options = {'tags': {'b'}}
        sanitizer = Nh3Sanitizer(nh3_options=custom_options)
        html_to_clean = "<p>文本</p><b>加粗</b><i>斜体</i>"
        clean_html = sanitizer.sanitize(html_to_clean)
        # <p> 和 <i> 标签被移除
        self.assertEqual(clean_html, "文本<b>加粗</b>斜体")

    def test_empty_string_remains_empty(self):
        """
        测试：输入空字符串应返回空字符串。
        """
        sanitizer = Nh3Sanitizer()
        self.assertEqual(sanitizer.sanitize(""), "")


class TestHtmlEscapeSanitizer(TestCase):
    """
    测试 HtmlEscapeSanitizer 的功能，它应该转义所有HTML特殊字符。
    """

    def test_escapes_all_special_html_characters(self):
        """
        测试：应转义 < > & ' " 所有五种HTML特殊字符。
        """
        escaper = HtmlEscapeSanitizer()
        raw_string = "<strong attr='value' & attr2=\"value2\">"
        escaped_string = escaper.sanitize(raw_string)
        self.assertEqual(escaped_string, "&lt;strong attr=&#39;value&#39; &amp; attr2=&#34;value2&#34;&gt;")

    def test_does_not_affect_normal_text(self):
        """
        测试：不包含特殊字符的普通文本不应被改变。
        """
        escaper = HtmlEscapeSanitizer()
        text = "这是一个普通的句子，没有任何特殊字符。"
        self.assertEqual(escaper.sanitize(text), text)

    def test_handles_non_string_input_gracefully(self):
        """
        测试：输入非字符串内容（如数字、None）时，应能正常处理而不会崩溃。
        """
        escaper = HtmlEscapeSanitizer()
        self.assertEqual(escaper.sanitize(123), "123")
        self.assertEqual(escaper.sanitize(None), "None")
        self.assertEqual(escaper.sanitize(True), "True")
