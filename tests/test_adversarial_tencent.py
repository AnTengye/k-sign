import math
import unittest
from unittest.mock import MagicMock
import ljd


class TencentCaptchaAdversarialTests(unittest.TestCase):
    """对抗性压力测试：验证 _extract_tencent_piece 在极端异常状态下的鲁棒性"""

    def test_extract_piece_empty_inputs_never_raise_stopiteration(self):
        """测试各种空输入与非 dict 输入，必须抛出受控的 ValueError，绝不抛出 StopIteration"""
        empty_adversarial_cases = [
            {"items": []},
            {},
            None,
            [],
            "",
            12345,
            set(),
            {"other_key": 123},
        ]
        for case in empty_adversarial_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError) as cm:
                    ljd.LJDSign._extract_tencent_piece(case)
                self.assertNotIsInstance(cm.exception, StopIteration)
                self.assertIn("未找到有效的滑块拼图块元素", str(cm.exception))

    def test_extract_piece_malformed_items_never_raise_stopiteration(self):
        """测试 items 列表中包含 malformed 项（None、空字典、字符串、缺失键、图片为 none/空）"""
        malformed_cases = [
            {"items": [None]},
            {"items": [None, None]},
            {"items": ["malformed_string_item"]},
            {"items": [123, 45.6, True, False, [], ()]},
            {"items": [{}]},
            {"items": [{"unrelated": "key"}]},
            {"items": [{"image": None, "w": 40, "h": 40}]},
            {"items": [{"image": "none", "w": 40, "h": 40}]},
            {"items": [{"image": "", "w": 40, "h": 40}]},
            {"items": [{"image": "url('x.png')"}]},  # 缺少 w 和 h
            {"items": [{"image": "url('x.png')", "w": 40}]},  # 缺少 h
            {"items": [{"image": "url('x.png')", "h": 40}]},  # 缺少 w
            {"items": [{"image": "none", "w": 0, "h": 0}]},
            {"items": [{"image": "url('x.png')", "w": float("nan"), "h": float("nan")}]},
            {"items": [{"image": "url('x.png')", "w": float("inf"), "h": float("inf")}]},
        ]
        for case in malformed_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError) as cm:
                    ljd.LJDSign._extract_tencent_piece(case)
                self.assertNotIsInstance(cm.exception, StopIteration)
                self.assertIn("未找到有效的滑块拼图块元素", str(cm.exception))

    def test_extract_piece_non_square_rectangular_rejected(self):
        """测试非正方形矩形尺寸（如 40x80、80x40 等）必须被拒绝，绝不抛出 StopIteration"""
        non_square_cases = [
            {"items": [{"image": "url('x.png')", "w": 40.0, "h": 80.0}]},
            {"items": [{"image": "url('x.png')", "w": 80.0, "h": 40.0}]},
            {"items": [{"image": "url('x.png')", "w": 1.0, "h": 100.0}]},
            {"items": [{"image": "url('x.png')", "w": 680.0, "h": 390.0}]},  # 背景图尺寸混入 items
            {"items": [{"image": "url('x.png')", "w": 40.0, "h": 41.0}]},   # 差值刚好为 1.0，应被拒绝
            {"items": [{"image": "url('x.png')", "w": 40.0, "h": 41.001}]}, # 差值大于 1.0
        ]
        for case in non_square_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError) as cm:
                    ljd.LJDSign._extract_tencent_piece(case)
                self.assertNotIsInstance(cm.exception, StopIteration)
                self.assertIn("未找到有效的滑块拼图块元素", str(cm.exception))

    def test_extract_piece_zero_or_negative_dimensions_rejected(self):
        """测试 0 或负数尺寸必须被拒绝"""
        invalid_dim_cases = [
            {"items": [{"image": "url('x.png')", "w": 0.0, "h": 0.0}]},
            {"items": [{"image": "url('x.png')", "w": 0.0, "h": 40.0}]},
            {"items": [{"image": "url('x.png')", "w": 40.0, "h": 0.0}]},
            {"items": [{"image": "url('x.png')", "w": -40.0, "h": -40.0}]},
        ]
        for case in invalid_dim_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError) as cm:
                    ljd.LJDSign._extract_tencent_piece(case)
                self.assertNotIsInstance(cm.exception, StopIteration)

    def test_extract_piece_mixed_valid_and_invalid_items(self):
        """测试混杂大量无效、畸变项后紧跟有效正方形拼图，能准确定位并提取该拼图"""
        valid_item = {
            "image": "url('https://t.captcha.qq.com/piece.png')",
            "size": "40px 40px",
            "pos": "-10px -20px",
            "w": 40.0,
            "h": 40.0,
            "left": 10.0,
            "top": 20.0,
        }
        meta = {
            "items": [
                None,
                "garbage",
                12345,
                {},
                {"image": None},
                {"image": "none", "w": 40.0, "h": 40.0},
                {"image": "url('bg.png')", "w": 680.0, "h": 390.0},
                {"image": "url('rect.png')", "w": 40.0, "h": 80.0},
                {"image": "url('zero.png')", "w": 0.0, "h": 0.0},
                valid_item,
                {"image": "url('second_valid.png')", "w": 40.0, "h": 40.0},
            ]
        }
        extracted = ljd.LJDSign._extract_tencent_piece(meta)
        self.assertEqual(valid_item, extracted)

    def test_extract_piece_float_near_square_accepted(self):
        """测试浏览器高分屏或缩放下微小亚像素偏差（|w - h| < 1）正常接受"""
        item = {
            "image": "url('piece.png')",
            "w": 40.4,
            "h": 40.0,
        }
        extracted = ljd.LJDSign._extract_tencent_piece({"items": [item]})
        self.assertEqual(item, extracted)

    def test_extract_piece_under_stress_with_large_adversarial_stream(self):
        """高并发大量混淆数据流压力测试（12,000 个畸形项），验证提取性能与无异常逃逸"""
        junk_items = [
            None,
            "string",
            {},
            {"image": "none", "w": 40, "h": 40},
            {"image": "url('x')", "w": 40, "h": 80},
            {"image": "url('x')", "w": 0, "h": 0},
        ] * 2000
        target_item = {"image": "url('valid.png')", "w": 40.0, "h": 40.0, "target": True}
        meta = {"items": junk_items + [target_item]}
        extracted = ljd.LJDSign._extract_tencent_piece(meta)
        self.assertTrue(extracted.get("target"))


    def _eval_ready_js(self, old_bg, dom_state):
        import json
        import subprocess

        js_script = ljd.LJDSign._TENCENT_CAPTCHA_READY_JS
        node_code = f"""
        const readyFn = {js_script};
        const domState = {json.dumps(dom_state)};
        const oldBg = {json.dumps(old_bg)};

        global.document = {{
            querySelector: (sel) => domState.elements[sel] || null,
            querySelectorAll: (sel) => domState.elements[sel] || []
        }};
        global.getComputedStyle = (el) => el.style || {{}};

        const result = readyFn(oldBg);
        process.stdout.write(JSON.stringify(result));
        """
        proc = subprocess.run(["node", "-e", node_code], capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)

    def test_ready_js_background_edge_conditions(self):
        """测试 _TENCENT_CAPTCHA_READY_JS 在背景图缺失、为 none、渐变、宽度为 0 时的拒绝判定"""
        # 1. 元素缺失
        self.assertFalse(self._eval_ready_js(None, {"elements": {}}))

        # 2. 背景图为空字符串
        self.assertFalse(self._eval_ready_js(None, {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": "", "width": "680px"}},
                ".tc-fg-item": [{"style": {"backgroundImage": "url('p.png')", "width": "40px", "height": "40px"}}],
            }
        }))

        # 3. 背景图为 none
        self.assertFalse(self._eval_ready_js(None, {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": "none", "width": "680px"}},
                ".tc-fg-item": [{"style": {"backgroundImage": "url('p.png')", "width": "40px", "height": "40px"}}],
            }
        }))

        # 4. 背景图不是 url() 形式（例如 linear-gradient）
        self.assertFalse(self._eval_ready_js(None, {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": "linear-gradient(to right, red, yellow)", "width": "680px"}},
                ".tc-fg-item": [{"style": {"backgroundImage": "url('p.png')", "width": "40px", "height": "40px"}}],
            }
        }))

        # 5. 背景图宽度 <= 0
        self.assertFalse(self._eval_ready_js(None, {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": "url('bg.png')", "width": "0px"}},
                ".tc-fg-item": [{"style": {"backgroundImage": "url('p.png')", "width": "40px", "height": "40px"}}],
            }
        }))

    def test_ready_js_reload_transition_lifecycle(self):
        """测试换题重试 (#reload) 时的生命周期状态变迁：oldBg -> none/清空 -> 新图加载中 -> 新图就绪"""
        old_bg = "url('https://t.captcha.qq.com/old_bg.png')"
        new_bg = "url('https://t.captcha.qq.com/new_bg.png')"
        fg_item_ready = {"style": {"backgroundImage": "url('piece.png')", "width": "40px", "height": "40px"}}

        # 状态 1：刚刚点击 reload，DOM 尚未变化，背景仍为旧图 -> 拒绝（避免读到上一题失效图片）
        state_old = {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": old_bg, "width": "680px"}},
                ".tc-fg-item": [fg_item_ready],
            }
        }
        self.assertFalse(self._eval_ready_js(old_bg, state_old))

        # 状态 2：reload 响应中，旧图被清空为 none -> 拒绝
        state_cleared = {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": "none", "width": "680px"}},
                ".tc-fg-item": [fg_item_ready],
            }
        }
        self.assertFalse(self._eval_ready_js(old_bg, state_cleared))

        # 状态 3：新背景图已就绪，但拼图块 fg 尚未完成图片渲染（none） -> 拒绝
        state_fg_pending = {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": new_bg, "width": "680px"}},
                ".tc-fg-item": [{"style": {"backgroundImage": "none", "width": "40px", "height": "40px"}}],
            }
        }
        self.assertFalse(self._eval_ready_js(old_bg, state_fg_pending))

        # 状态 4：新背景图就绪，且正方形拼图块也完成渲染 -> 判定就绪 (True)
        state_all_ready = {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": new_bg, "width": "680px"}},
                ".tc-fg-item": [fg_item_ready],
            }
        }
        self.assertTrue(self._eval_ready_js(old_bg, state_all_ready))

    def test_ready_js_fg_item_dimensions_and_mixed_items(self):
        """测试 fg 拼图块尺寸不匹配（非方形、0尺寸）及多项混合时的就绪判断"""
        bg = "url('https://t.captcha.qq.com/bg.png')"

        # 1. 拼图块非正方形 (40x80) -> 拒绝
        self.assertFalse(self._eval_ready_js(None, {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": bg, "width": "680px"}},
                ".tc-fg-item": [{"style": {"backgroundImage": "url('p.png')", "width": "40px", "height": "80px"}}],
            }
        }))

        # 2. 拼图块 0 尺寸 -> 拒绝
        self.assertFalse(self._eval_ready_js(None, {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": bg, "width": "680px"}},
                ".tc-fg-item": [{"style": {"backgroundImage": "url('p.png')", "width": "0px", "height": "0px"}}],
            }
        }))

        # 3. 多个 .tc-fg-item 混合存在（包含全幅阴影条 680x390、非方形块与正方形拼图块） -> 命中有效正方形
        self.assertTrue(self._eval_ready_js(None, {
            "elements": {
                "#slideBg": {"style": {"backgroundImage": bg, "width": "680px"}},
                ".tc-fg-item": [
                    {"style": {"backgroundImage": "none", "width": "680px", "height": "390px"}},
                    {"style": {"backgroundImage": "url('rect.png')", "width": "40px", "height": "80px"}},
                    {"style": {"backgroundImage": "url('valid.png')", "width": "40px", "height": "40.2px"}},
                ],
            }
        }))


if __name__ == "__main__":
    unittest.main()
