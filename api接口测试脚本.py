#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科普文章API接口测试脚本
直接测试 /api/public/science/* 接口功能
"""

import requests
import json
import time
from typing import Dict, Any, List

class APITester:
    """API接口测试器"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/public/science"
        self.test_results = []

    def log_test(self, test_name: str, success: bool, message: str, data: Any = None):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "data": data
        }
        self.test_results.append(result)

        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")

        if data and not success:
            print(f"   响应数据: {json.dumps(data, indent=4, ensure_ascii=False)}")

    def test_get_articles(self):
        """测试获取文章列表接口"""
        print("\n🔍 测试获取文章列表接口...")

        # 测试1: 基本列表查询
        try:
            response = requests.get(f"{self.api_base}/articles")
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "基本文章列表查询",
                    data.get("success", False),
                    data.get("message", "无消息"),
                    data.get("data")
                )
            else:
                self.log_test(
                    "基本文章列表查询",
                    False,
                    f"HTTP状态码: {response.status_code}"
                )
        except Exception as e:
            self.log_test("基本文章列表查询", False, f"请求异常: {str(e)}")

        # 测试2: 带分页参数
        try:
            response = requests.get(f"{self.api_base}/articles?page=1&size=3")
            if response.status_code == 200:
                data = response.json()
                success = (data.get("success", False) and
                          data.get("data", {}).get("size") == 3)
                self.log_test(
                    "分页参数测试",
                    success,
                    f"返回页大小: {data.get('data', {}).get('size', '未知')}"
                )
        except Exception as e:
            self.log_test("分页参数测试", False, f"请求异常: {str(e)}")

        # 测试3: 关键词搜索
        try:
            response = requests.get(f"{self.api_base}/articles?keyword=科学")
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "关键词搜索测试",
                    data.get("success", False),
                    f"搜索结果数量: {data.get('data', {}).get('total', 0)}"
                )
        except Exception as e:
            self.log_test("关键词搜索测试", False, f"请求异常: {str(e)}")

        # 测试4: 作者筛选
        try:
            response = requests.get(f"{self.api_base}/articles?author_account=admin")
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "作者筛选测试",
                    data.get("success", False),
                    f"筛选结果数量: {data.get('data', {}).get('total', 0)}"
                )
        except Exception as e:
            self.log_test("作者筛选测试", False, f"请求异常: {str(e)}")

    def test_get_article_detail(self):
        """测试获取文章详情接口"""
        print("\n📄 测试获取文章详情接口...")

        # 先获取一个文章ID
        article_id = None
        try:
            response = requests.get(f"{self.api_base}/articles?size=1")
            if response.status_code == 200:
                data = response.json()
                items = data.get("data", {}).get("items", [])
                if items:
                    article_id = items[0]["id"]
        except:
            pass

        if not article_id:
            self.log_test("获取文章详情", False, "无法获取测试文章ID")
            return

        # 测试正常文章详情
        try:
            response = requests.get(f"{self.api_base}/articles/{article_id}")
            if response.status_code == 200:
                data = response.json()
                success = (data.get("success", False) and
                          data.get("data", {}).get("id") == article_id)
                self.log_test(
                    "获取文章详情",
                    success,
                    f"文章标题: {data.get('data', {}).get('title', '未知')}"
                )
            else:
                self.log_test(
                    "获取文章详情",
                    False,
                    f"HTTP状态码: {response.status_code}"
                )
        except Exception as e:
            self.log_test("获取文章详情", False, f"请求异常: {str(e)}")

        # 测试不存在的文章
        try:
            response = requests.get(f"{self.api_base}/articles/99999")
            if response.status_code == 404:
                data = response.json()
                self.log_test(
                    "不存在文章测试",
                    not data.get("success", True),
                    data.get("message", "正确返回404")
                )
            else:
                self.log_test(
                    "不存在文章测试",
                    False,
                    f"期望404，实际状态码: {response.status_code}"
                )
        except Exception as e:
            self.log_test("不存在文章测试", False, f"请求异常: {str(e)}")

    def test_get_statistics(self):
        """测试获取统计信息接口"""
        print("\n📊 测试获取统计信息接口...")

        try:
            response = requests.get(f"{self.api_base}/articles/statistics")
            if response.status_code == 200:
                data = response.json()
                success = (data.get("success", False) and
                          data.get("data") is not None)

                stats_data = data.get("data", {})
                required_fields = ["total_published", "total_likes", "total_views"]
                has_required_fields = all(field in stats_data for field in required_fields)

                self.log_test(
                    "获取统计信息",
                    success and has_required_fields,
                    f"统计字段完整: {has_required_fields}",
                    stats_data
                )
            else:
                self.log_test(
                    "获取统计信息",
                    False,
                    f"HTTP状态码: {response.status_code}"
                )
        except Exception as e:
            self.log_test("获取统计信息", False, f"请求异常: {str(e)}")

    def test_response_format(self):
        """测试响应格式规范"""
        print("\n📋 测试响应格式规范...")

        try:
            response = requests.get(f"{self.api_base}/articles")
            if response.status_code == 200:
                data = response.json()

                # 检查基本响应结构
                has_success = "success" in data
                has_message = "message" in data
                has_data = "data" in data

                format_ok = has_success and has_message and has_data

                self.log_test(
                    "响应格式规范",
                    format_ok,
                    f"success: {has_success}, message: {has_message}, data: {has_data}"
                )

                # 如果有数据，检查分页格式
                if format_ok and data.get("success") and data.get("data"):
                    data_obj = data["data"]
                    has_pagination = ("items" in data_obj and
                                    "total" in data_obj and
                                    "page" in data_obj and
                                    "size" in data_obj)

                    self.log_test(
                        "分页数据格式",
                        has_pagination,
                        f"分页字段完整: {has_pagination}"
                    )
        except Exception as e:
            self.log_test("响应格式规范", False, f"请求异常: {str(e)}")

    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始科普文章API接口测试")
        print(f"测试目标: {self.api_base}")
        print("=" * 60)

        # 检查服务是否可用
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                print("✅ 服务连接正常")
            else:
                print(f"⚠️ 服务状态码: {response.status_code}")
        except Exception as e:
            print(f"❌ 服务连接失败: {str(e)}")
            print("请确保Flask服务正在运行")
            return

        # 运行各项测试
        self.test_get_articles()
        self.test_get_article_detail()
        self.test_get_statistics()
        self.test_response_format()

        # 输出测试总结
        self.print_summary()

    def print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("📋 测试总结")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests

        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests} ✅")
        print(f"失败: {failed_tests} ❌")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%")

        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   • {result['test_name']}: {result['message']}")

        print("\n✅ 测试完成!")


def main():
    """主函数"""
    # 可以通过命令行参数指定不同的URL
    import sys
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"

    tester = APITester(base_url)
    tester.run_all_tests()


if __name__ == "__main__":
    main()