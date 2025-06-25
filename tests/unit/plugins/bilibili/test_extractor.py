"""B站视频提取器测试模块。

该模块包含对BilibiliExtractor类的单元测试。
"""

import os
import json
import time
import pytest
from unittest.mock import Mock, patch
from requests.exceptions import Timeout, RequestException
from src.plugins.bilibili.extractor import BilibiliExtractor
from .mock_utils import MockResponse, create_video_response

class TestBilibiliExtractor:
    """B站视频提取器测试类。"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, tmp_path, mocker):
        """测试前置和后置操作。
        
        Args:
            tmp_path: pytest提供的临时目录路径
            mocker: pytest-mock提供的mocker
        """
        # 设置
        self.extractor = BilibiliExtractor()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "../../../fixtures")
        
        # 创建测试数据目录
        os.makedirs(self.fixtures_dir, exist_ok=True)
        
        # Mock代理设置
        self.extractor.proxy = None
        
        # 加载测试数据
        self.test_samples = self._load_test_samples()
        
        # 记录所有mock
        self.mocks = []
        
        yield
        
        # 清理所有mock
        for mock in self.mocks:
            mock.stop()
            
    def _create_mock(self, target, **kwargs):
        """创建并记录mock对象。
        
        Args:
            target: 要mock的对象
            **kwargs: mock的参数
            
        Returns:
            Mock: mock对象
        """
        mock = patch(target, **kwargs)
        self.mocks.append(mock)
        return mock.start()
        
    def _load_fixture(self, filename: str) -> str:
        """加载测试数据文件。
        
        Args:
            filename: 测试数据文件名
            
        Returns:
            str: 文件内容
        """
        path = os.path.join(self.fixtures_dir, filename)
        with open(path, encoding='utf-8') as f:
            return f.read()
            
    def _load_test_samples(self) -> dict:
        """加载测试样例数据。
        
        Returns:
            dict: 测试样例数据
        """
        return json.loads(self._load_fixture("video_samples.json"))
            
    def _mock_response(self, status_code=200, json_data=None, text=None):
        """创建Mock响应对象。
        
        Args:
            status_code: HTTP状态码
            json_data: JSON响应数据
            text: 文本响应数据
        
        Returns:
            Mock: Mock响应对象
        """
        mock_resp = Mock()
        mock_resp.status_code = status_code
        mock_resp.raise_for_status = Mock()
        
        if status_code != 200:
            mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
            
        if json_data is not None:
            mock_resp.json = Mock(return_value=json_data)
            
        if text is not None:
            mock_resp.text = text
            
        return mock_resp
        
    @pytest.mark.parametrize("url,expected", [
        ("https://www.bilibili.com/video/BV1xx411c7mD", "BV1xx411c7mD"),
        ("https://b23.tv/BV1xx411c7mD", "BV1xx411c7mD"),
        ("https://www.bilibili.com/video/av114514", None),
        ("https://www.invalid.com", None),
    ])
    def test_extract_bvid(self, url, expected):
        """测试BV号提取。
        
        Args:
            url: 输入URL
            expected: 期望的BV号
        """
        assert self.extractor._extract_bvid(url) == expected, \
            f"从URL {url} 提取BV号失败，期望得到 {expected}"
        
    @pytest.mark.parametrize("quality_data,expected", [
        (
            {"accept_quality": [126, 116, 80, 64, 32, 16]},
            {
                126: "Dolby Vision",
                116: "1080p60",
                80: "1080p",
                64: "720p",
                32: "480p",
                16: "360p"
            }
        ),
        (
            {"accept_quality": [80, 64, 32]},
            {
                80: "1080p",
                64: "720p",
                32: "480p"
            }
        ),
        (
            {"accept_quality": [999]},  # 测试未知代码
            {999: "未知(999)"}
        ),
        (
            {"accept_quality": []},
            {}
        ),
        (
            {},  # 测试缺失字段
            {}
        ),
    ])
    def test_extract_qualities(self, quality_data, expected):
        """测试视频质量列表提取。
        
        Args:
            quality_data: 输入的质量数据
            expected: 期望的质量映射
        """
        result = self.extractor._extract_qualities(quality_data)
        assert result == expected, \
            f"清晰度映射提取错误，输入: {quality_data}，期望: {expected}，实际: {result}"
            
    def test_quality_map_completeness(self):
        """测试清晰度映射表的完整性。"""
        # 验证所有大会员清晰度
        vip_qualities = {127, 126, 120, 116, 112}
        for code in vip_qualities:
            assert code in self.extractor.QUALITY_MAP, f"缺少大会员清晰度 {code}"
            
        # 验证所有登录用户清晰度
        login_qualities = {80, 74, 64}
        for code in login_qualities:
            assert code in self.extractor.QUALITY_MAP, f"缺少登录用户清晰度 {code}"
            
        # 验证所有免费清晰度
        free_qualities = {32, 16}
        for code in free_qualities:
            assert code in self.extractor.QUALITY_MAP, f"缺少免费清晰度 {code}"
            
    def test_quality_map_naming(self):
        """测试清晰度名称格式。"""
        for code, name in self.extractor.QUALITY_MAP.items():
            # 验证名称格式
            assert isinstance(name, str), f"清晰度 {code} 的名称应该是字符串"
            assert len(name) > 0, f"清晰度 {code} 的名称不能为空"
            assert name == name.strip(), f"清晰度 {code} 的名称不应有多余空格"
            
            # 验证特殊清晰度名称
            if code == 127:
                assert name == "8K", "代码127应该对应8K"
            elif code == 126:
                assert name == "Dolby Vision", "代码126应该对应Dolby Vision"
            elif code == 120:
                assert name == "4K", "代码120应该对应4K"
                
    def test_extract_info_with_qualities(self, mocker):
        """测试视频信息提取中的清晰度信息。"""
        # Mock API响应
        video_info = {
            "code": 0,
            "data": {
                "bvid": "BV1xx411c7mD",
                "title": "测试视频",
                "owner": {"name": "测试UP主"}
            }
        }
        
        play_info = {
            "code": 0,
            "data": {
                "accept_quality": [116, 80, 64, 32],
                "accept_description": ["1080p60", "1080p", "720p", "480p"]
            }
        }
        
        # 设置Mock
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            MockResponse(json_data=video_info),
            MockResponse(json_data=play_info)
        ]
        
        # 测试提取
        info = self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
        
        # 验证清晰度信息
        assert isinstance(info["qualities"], dict), "清晰度信息应该是字典类型"
        assert 116 in info["qualities"], "应该包含1080p60清晰度"
        assert info["qualities"][116] == "1080p60", "1080p60清晰度名称错误"
        assert len(info["qualities"]) == 4, "清晰度数量不正确"
        
    def test_vip_quality_without_login(self, mocker):
        """测试未登录时请求大会员清晰度。"""
        # Mock API响应
        video_info = {
            "code": 0,
            "data": {
                "bvid": "BV1xx411c7mD",
                "title": "测试视频",
                "owner": {"name": "测试UP主"}
            }
        }
        
        play_info = {
            "code": -404,
            "message": "该清晰度需要大会员"
        }
        
        # 设置Mock
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            MockResponse(json_data=video_info),
            MockResponse(json_data=play_info)
        ]
        
        # 测试提取
        with pytest.raises(VIPContentError) as exc_info:
            self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            
        assert "大会员专享" in str(exc_info.value), "应该提示需要大会员"
        
    @pytest.mark.parametrize("sample_key", ["normal", "missing_data", "anti_crawl"])
    def test_parse_html(self, sample_key):
        """测试HTML解析。
        
        Args:
            sample_key: 测试样例键名
        """
        sample = self.test_samples[sample_key]
        result = self.extractor._parse_html(sample["html"])
        
        if sample["expected"] is None:
            assert result is None, \
                f"对于无效HTML（{sample_key}），期望返回None"
        else:
            assert result is not None, \
                f"HTML解析失败（{sample_key}）"
            for key, value in sample["expected"].items():
                assert result[key] == value, \
                    f"字段 {key} 解析错误，期望 {value}，实际得到 {result.get(key)}"
                    
    def test_invalid_html(self):
        """测试无效HTML输入。"""
        broken_html = "<div>无效内容</div>"
        result = self.extractor._parse_html(broken_html)
        assert result is None, \
            "对于无效的HTML内容，应该返回None"
            
    @patch('requests.get')
    def test_anti_crawl_handling(self, mock_get):
        """测试反爬虫机制处理。"""
        # 模拟反爬响应
        anti_crawl_response = self._mock_response(
            status_code=412,
            text=self.test_samples["anti_crawl"]["html"]
        )
        mock_get.return_value = anti_crawl_response
        
        with pytest.raises(RuntimeError) as exc_info:
            self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            
        assert "请求被拦截" in str(exc_info.value), \
            "应该正确处理反爬虫响应"
            
    @patch('requests.get')
    def test_extract_video_info_success(self, mock_get):
        """测试成功提取普通视频信息。"""
        # 模拟API响应
        video_info = {
            "code": 0,
            "data": {
                "bvid": "BV1xx411c7mD",
                "aid": 114514,
                "title": "测试视频",
                "desc": "视频描述",
                "owner": {
                    "mid": 1919810,
                    "name": "测试UP主"
                },
                "stat": {
                    "view": 1000,
                    "like": 100
                },
                "duration": 180,
                "pic": "http://test.com/cover.jpg",
                "cid": 12345
            }
        }
        
        playurl_info = {
            "code": 0,
            "data": {
                "accept_quality": [116, 80, 64, 32],
                "support_formats": [
                    {"quality": 116, "format": "1080P 60帧"},
                    {"quality": 80, "format": "1080P"},
                    {"quality": 64, "format": "720P"},
                    {"quality": 32, "format": "480P"}
                ]
            }
        }
        
        mock_get.side_effect = [
            self._mock_response(json_data=video_info),
            self._mock_response(json_data=playurl_info)
        ]
        
        # 测试提取
        info = self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
        
        assert info["title"] == "测试视频", "视频标题提取错误"
        assert info["author"] == "测试UP主", "UP主名称提取错误"
        assert info["duration"] == 180, "视频时长提取错误"
        assert info["qualities"] == ["1080P60", "1080P", "720P", "480P"], \
            "视频清晰度列表提取错误"
        assert info["play_count"] == 1000, "播放量提取错误"
        assert info["like_count"] == 100, "点赞数提取错误"
        
    @patch('requests.get')
    def test_extract_video_info_fail(self, mock_get):
        """测试提取视频信息失败的情况。"""
        mock_get.return_value = self._mock_response(
            status_code=404,
            json_data={"code": -404, "message": "啥都木有"}
        )
        
        with pytest.raises(RuntimeError, match="API请求失败") as exc_info:
            self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            
        assert "啥都木有" in str(exc_info.value), \
            "应该包含API返回的错误信息"
            
    def test_invalid_url(self):
        """测试无效URL。"""
        with pytest.raises(ValueError, match="无效的视频URL") as exc_info:
            self.extractor.extract_info("https://www.invalid.com")
            
        assert "无效的视频URL" in str(exc_info.value), \
            "应该提示无效的视频URL"
            
    @pytest.mark.parametrize("retry_count,expected_success", [
        (1, False),  # 第一次重试失败
        (2, True),   # 第二次重试成功
    ])
    @patch('requests.get')
    def test_retry_mechanism(self, mock_get, retry_count, expected_success):
        """测试重试机制。
        
        Args:
            mock_get: Mock的requests.get函数
            retry_count: 重试次数
            expected_success: 是否期望成功
        """
        # 准备响应序列
        responses = [
            self._mock_response(status_code=412, text=self.test_samples["anti_crawl"]["html"])
        ] * retry_count
        
        if expected_success:
            responses.append(self._mock_response(
                json_data={"code": 0, "data": {"title": "测试视频"}}
            ))
            
        mock_get.side_effect = responses
        
        if expected_success:
            result = self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            assert result is not None, "重试后应该成功获取数据"
        else:
            with pytest.raises(RuntimeError) as exc_info:
                self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            assert "请求被拦截" in str(exc_info.value), \
                "重试失败后应该抛出异常"
            
    def test_api_request_mock(self, mocker):
        """测试API请求mock。"""
        mock_response = create_video_response(
            title="Mock视频",
            duration=120,
            author="Mock UP主"
        )
        
        mocker.patch("requests.get", return_value=mock_response)
        
        result = self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
        assert result["title"] == "Mock视频", "视频标题不匹配"
        assert result["duration"] == 120, "视频时长不匹配"
        assert result["author"] == "Mock UP主", "UP主名称不匹配"
        
    @pytest.mark.parametrize("status_code,expected_error", [
        (403, "HTTP 403"),
        (404, "HTTP 404"),
        (500, "HTTP 500"),
    ])
    def test_error_status_codes(self, mocker, status_code, expected_error):
        """测试错误状态码处理。
        
        Args:
            mocker: pytest-mock提供的mocker
            status_code: HTTP状态码
            expected_error: 期望的错误信息
        """
        mock_response = create_video_response(status_code=status_code)
        mocker.patch("requests.get", return_value=mock_response)
        
        with pytest.raises(RuntimeError) as exc_info:
            self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            
        assert expected_error in str(exc_info.value), \
            f"应该包含错误状态码 {status_code} 的信息"
            
    @pytest.mark.parametrize("delay,should_timeout", [
        (2.5, False),  # 接近但未超时
        (3.5, True),   # 超时
        (5.0, True),   # 明显超时
    ])
    def test_network_delays(self, mocker, delay, should_timeout):
        """测试网络延迟处理。
        
        Args:
            mocker: pytest-mock提供的mocker
            delay: 模拟的网络延迟（秒）
            should_timeout: 是否应该超时
        """
        mock_response = create_video_response(delay=delay)
        mocker.patch("requests.get", return_value=mock_response)
        
        if should_timeout:
            with pytest.raises(Timeout) as exc_info:
                self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            assert f"timed out after {delay} seconds" in str(exc_info.value), \
                "应该提示请求超时"
        else:
            result = self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            assert result is not None, "未超时时应该返回结果"
            
    def test_network_errors(self, mocker):
        """测试网络错误处理。"""
        # 模拟连接错误
        mocker.patch("requests.get", side_effect=RequestException("连接失败"))
        
        with pytest.raises(RuntimeError) as exc_info:
            self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            
        assert "连接失败" in str(exc_info.value), \
            "应该包含网络错误信息"
            
    def test_retry_on_error(self, mocker):
        """测试错误重试机制。"""
        # 前两次请求失败，第三次成功
        responses = [
            create_video_response(status_code=503),  # 服务暂时不可用
            create_video_response(status_code=429),  # 请求过多
            create_video_response(title="重试成功")  # 最后成功
        ]
        
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = responses
        
        result = self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
        
        assert result["title"] == "重试成功", "重试后应该返回正确结果"
        assert mock_get.call_count == 3, "应该尝试了3次请求"
        
    def test_json_parse_error(self, mocker):
        """测试JSON解析错误处理。"""
        # 返回无效的JSON数据
        mock_response = MockResponse(
            status_code=200,
            text="Invalid JSON",
            json_data=None
        )
        mocker.patch("requests.get", return_value=mock_response)
        
        with pytest.raises(RuntimeError) as exc_info:
            self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            
        assert "JSON解析失败" in str(exc_info.value), \
            "应该提示JSON解析错误"
            
    @pytest.mark.parametrize("sample_key,expected_cid", [
        ("normal", "12345678"),      # 正常情况
        ("missing_cid", None),       # CID不存在
        ("invalid_cid", None),       # 无效CID
        ("missing_data", None),      # 数据缺失
        ("anti_crawl", None),        # 反爬页面
    ])
    def test_get_video_cid(self, sample_key, expected_cid):
        """测试从HTML中提取CID。
        
        Args:
            sample_key: 测试样例键名
            expected_cid: 期望的CID值
        """
        sample = self.test_samples[sample_key]
        cid = self.extractor.get_video_cid(sample["html"])
        
        if expected_cid is None:
            assert cid is None, \
                f"对于{sample_key}场景，应该返回None，但得到了{cid}"
        else:
            assert cid == expected_cid, \
                f"CID提取错误，期望{expected_cid}，实际得到{cid}"
                
    def test_get_video_cid_from_api(self, mocker):
        """测试从API响应中提取CID。"""
        mock_response = create_video_response(
            bvid="BV1xx411c7mD",
            cid="87654321"
        )
        mocker.patch("requests.get", return_value=mock_response)
        
        cid = self.extractor.get_video_cid_from_api("BV1xx411c7mD")
        assert cid == "87654321", "从API响应中提取CID失败"
        
    def test_get_video_cid_with_retry(self, mocker):
        """测试CID提取的重试机制。"""
        # 模拟HTML解析失败后从API获取
        html_without_cid = self.test_samples["missing_cid"]["html"]
        mock_response = create_video_response(cid="98765432")
        
        mocker.patch("requests.get", return_value=mock_response)
        
        cid = self.extractor.get_video_cid(html_without_cid, retry_api=True)
        assert cid == "98765432", "重试从API获取CID失败"
        
    def test_get_video_cid_validation(self):
        """测试CID格式验证。"""
        invalid_html_samples = [
            # 空字符串
            "",
            # 无效JSON
            "<script>window.__INITIAL_STATE__=invalid_json</script>",
            # CID格式错误
            "<script>window.__INITIAL_STATE__={\"videoData\":{\"cid\":\"abc\"}}</script>",
            # CID为负数
            "<script>window.__INITIAL_STATE__={\"videoData\":{\"cid\":\"-123\"}}</script>",
            # CID为0
            "<script>window.__INITIAL_STATE__={\"videoData\":{\"cid\":\"0\"}}</script>",
        ]
        
        for html in invalid_html_samples:
            cid = self.extractor.get_video_cid(html)
            assert cid is None, \
                f"对于无效输入 '{html[:50]}...'，应该返回None"
                
    @pytest.mark.parametrize("api_response,expected_error", [
        ({"code": -404, "message": "视频不存在"}, "视频不存在"),
        ({"code": -403, "message": "访问权限不足"}, "访问权限不足"),
        ({"code": 0, "data": {}}, "未找到CID"),
        ({"code": 0, "data": {"cid": "invalid"}}, "无效的CID格式"),
    ])
    def test_get_video_cid_api_errors(self, mocker, api_response, expected_error):
        """测试API获取CID时的错误处理。
        
        Args:
            mocker: pytest-mock提供的mocker
            api_response: 模拟的API响应
            expected_error: 期望的错误信息
        """
        mock_response = MockResponse(
            status_code=200,
            json_data=api_response
        )
        mocker.patch("requests.get", return_value=mock_response)
        
        with pytest.raises(RuntimeError) as exc_info:
            self.extractor.get_video_cid_from_api("BV1xx411c7mD")
            
        assert expected_error in str(exc_info.value), \
            f"应该包含错误信息 '{expected_error}'"
            
    def test_get_video_cid_cache(self, mocker):
        """测试CID缓存机制。"""
        # 第一次调用
        mock_response = create_video_response(cid="11111111")
        mock_get = mocker.patch("requests.get", return_value=mock_response)
        
        cid1 = self.extractor.get_video_cid_from_api("BV1xx411c7mD")
        assert cid1 == "11111111", "首次获取CID失败"
        
        # 第二次调用应该使用缓存
        cid2 = self.extractor.get_video_cid_from_api("BV1xx411c7mD")
        assert cid2 == "11111111", "缓存的CID与首次获取不一致"
        assert mock_get.call_count == 1, "应该只调用一次API"
        
    @pytest.mark.benchmark(
        group="extractor",
        min_rounds=100,
        disable_gc=True,
        warmup=True
    )
    def test_get_video_cid_performance(self, benchmark):
        """测试CID提取性能。"""
        html = self.test_samples["normal"]["html"]
        
        def run_benchmark():
            return self.extractor.get_video_cid(html)
            
        result = benchmark(run_benchmark)
        assert result == "12345678", "基准测试应该返回正确的CID"
        
    @pytest.mark.benchmark(
        group="extractor",
        min_rounds=100
    )
    def test_get_video_info_performance(self, benchmark, mocker):
        """测试视频信息提取性能。"""
        mock_response = create_video_response(
            title="性能测试视频",
            duration=120,
            delay=0.001  # 模拟小延迟
        )
        mocker.patch("requests.get", return_value=mock_response)
        
        def run_benchmark():
            return self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            
        result = benchmark(run_benchmark)
        assert result["title"] == "性能测试视频", "基准测试应该返回正确的视频信息"
        
    @pytest.mark.parametrize("cache_size", [10, 100, 1000])
    def test_cid_cache_performance(self, benchmark, mocker, cache_size):
        """测试不同缓存大小下的性能。
        
        Args:
            benchmark: pytest-benchmark提供的benchmark工具
            mocker: pytest-mock提供的mocker
            cache_size: 缓存大小
        """
        # 设置缓存大小
        self.extractor.cache_size = cache_size
        
        # 准备测试数据
        mock_responses = {
            f"BV{i:010d}": create_video_response(cid=str(i))
            for i in range(cache_size * 2)  # 创建两倍于缓存大小的数据
        }
        
        def mock_get(*args, **kwargs):
            bvid = next(bv for bv in mock_responses.keys() if bv in args[0])
            return mock_responses[bvid]
            
        mocker.patch("requests.get", side_effect=mock_get)
        
        def run_benchmark():
            # 随机访问所有BV号，测试缓存命中率
            for bvid in mock_responses.keys():
                self.extractor.get_video_cid_from_api(bvid)
                
        benchmark(run_benchmark)
        
    def test_concurrent_requests(self, benchmark, mocker):
        """测试并发请求性能。"""
        from concurrent.futures import ThreadPoolExecutor
        import random
        
        # 模拟随机延迟的响应
        def delayed_response(*args, **kwargs):
            time.sleep(random.uniform(0.001, 0.01))
            return create_video_response()
            
        mocker.patch("requests.get", side_effect=delayed_response)
        
        def run_concurrent_requests():
            urls = [
                f"https://www.bilibili.com/video/BV{i:010d}"
                for i in range(10)
            ]
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(
                    self.extractor.extract_info,
                    urls
                ))
            return results
            
        results = benchmark(run_concurrent_requests)
        assert len(results) == 10, "应该成功处理所有并发请求"
        
    @pytest.mark.parametrize("test_case", [
        (
            "empty_cid",
            {"code": 0, "data": {"bvid": "BV1xx411c7mD", "title": "测试视频", "cid": None}},
            "视频CID不能为空"
        ),
        (
            "long_title",
            {
                "code": 0,
                "data": {
                    "bvid": "BV1xx411c7mD",
                    "title": "x" * 150,  # 超长标题
                    "cid": "12345"
                }
            },
            None  # 不应抛出异常，但标题应被截断
        ),
        (
            "invalid_danmaku",
            {
                "code": 0,
                "data": {
                    "bvid": "BV1xx411c7mD",
                    "title": "测试视频",
                    "cid": "12345",
                    "subtitle": {"list": [{"lan": "zh-CN", "subtitle_url": "invalid_xml"}]}
                }
            },
            "弹幕XML格式无效"
        )
    ], ids=["empty_cid", "long_title", "invalid_danmaku"])
    def test_edge_cases(self, mocker, test_case):
        """测试边界条件。
        
        Args:
            mocker: pytest-mock提供的mocker
            test_case: 测试用例元组(case_name, api_response, expected_error)
        """
        case_name, api_response, expected_error = test_case
        
        # Mock API响应
        mock_get = mocker.patch("requests.get")
        mock_get.return_value = self._mock_response(json_data=api_response)
        
        if expected_error:
            with pytest.raises(RuntimeError) as exc_info:
                self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            assert expected_error in str(exc_info.value), f"{case_name}：应该提示 {expected_error}"
        else:
            info = self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            if case_name == "long_title":
                assert len(info["title"]) <= 100, "超长标题应该被截断到100字符"
                
    def test_disk_space_error(self, mocker, tmp_path):
        """测试磁盘空间不足的情况。"""
        # Mock os.statvfs返回接近满的磁盘信息
        mock_statvfs = mocker.patch("os.statvfs")
        mock_statvfs.return_value = Mock(
            f_bsize=4096,  # 块大小
            f_blocks=1000000,  # 总块数
            f_bfree=100,  # 剩余块数（非常少）
            f_bavail=50  # 可用块数（更少）
        )
        
        # Mock视频信息返回大文件
        video_info = {
            "code": 0,
            "data": {
                "bvid": "BV1xx411c7mD",
                "title": "大文件测试",
                "cid": "12345",
                "duration": 3600,  # 1小时视频
                "pages": [{"size": 1024 * 1024 * 1024}]  # 1GB大小
            }
        }
        
        mock_get = mocker.patch("requests.get")
        mock_get.return_value = self._mock_response(json_data=video_info)
        
        with pytest.raises(RuntimeError) as exc_info:
            self.extractor.extract_info("https://www.bilibili.com/video/BV1xx411c7mD")
            
        assert "磁盘空间不足" in str(exc_info.value), "应该提示磁盘空间不足" 