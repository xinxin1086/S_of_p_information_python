#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科普文章API使用示例
演示如何使用 /api/public/science/* 接口
"""

import requests
import json
from typing import Dict, Any, Optional

# API基础配置
BASE_URL = "http://localhost:5000"  # 根据实际部署地址调整
API_BASE = f"{BASE_URL}/api/public/science"

class ScienceArticleAPI:
    """科普文章API客户端"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/public/science"

    def get_articles(self,
                    page: int = 1,
                    size: int = 10,
                    keyword: str = "",
                    author_account: str = "") -> Dict[str, Any]:
        """
        获取科普文章列表

        Args:
            page: 页码，默认1
            size: 每页数量，默认10
            keyword: 关键词搜索（标题和内容）
            author_account: 作者账号筛选

        Returns:
            API响应数据
        """
        params = {
            'page': page,
            'size': size
        }

        if keyword:
            params['keyword'] = keyword
        if author_account:
            params['author_account'] = author_account

        try:
            response = requests.get(f"{self.api_base}/articles", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"请求失败: {str(e)}", "data": None}

    def get_article_detail(self, article_id: int) -> Dict[str, Any]:
        """
        获取科普文章详情

        Args:
            article_id: 文章ID

        Returns:
            API响应数据
        """
        try:
            response = requests.get(f"{self.api_base}/articles/{article_id}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"请求失败: {str(e)}", "data": None}

    def get_articles_statistics(self) -> Dict[str, Any]:
        """
        获取科普文章统计信息

        Returns:
            API响应数据
        """
        try:
            response = requests.get(f"{self.api_base}/articles/statistics")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"请求失败: {str(e)}", "data": None}


def demo_api_usage():
    """演示API使用"""
    print("=== 科普文章API使用演示 ===\n")

    api = ScienceArticleAPI()

    # 1. 获取文章列表
    print("1. 获取科普文章列表")
    result = api.get_articles(page=1, size=5)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    # 2. 关键词搜索
    print("2. 关键词搜索科普文章")
    result = api.get_articles(page=1, size=3, keyword="科学")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    # 3. 获取统计信息
    print("3. 获取科普文章统计信息")
    result = api.get_articles_statistics()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    # 4. 获取文章详情（如果有文章的话）
    print("4. 获取文章详情")
    # 先获取文章列表找一个文章ID
    articles_result = api.get_articles(page=1, size=1)
    if (articles_result.get("success") and
        articles_result.get("data", {}).get("items")):

        article_id = articles_result["data"]["items"][0]["id"]
        print(f"获取文章ID {article_id} 的详情:")

        detail_result = api.get_article_detail(article_id)
        print(json.dumps(detail_result, indent=2, ensure_ascii=False))
    else:
        print("没有找到可用的文章")


def curl_commands():
    """生成curl命令示例"""
    print("=== curl命令示例 ===\n")

    base_url = "http://localhost:5000"

    print("1. 获取科普文章列表:")
    print(f"curl -X GET \"{base_url}/api/public/science/articles?page=1&size=5\"")
    print()

    print("2. 关键词搜索:")
    print(f"curl -X GET \"{base_url}/api/public/science/articles?page=1&size=10&keyword=科学\"")
    print()

    print("3. 作者筛选:")
    print(f"curl -X GET \"{base_url}/api/public/science/articles?page=1&size=10&author_account=admin\"")
    print()

    print("4. 获取文章详情:")
    print(f"curl -X GET \"{base_url}/api/public/science/articles/1\"")
    print()

    print("5. 获取统计信息:")
    print(f"curl -X GET \"{base_url}/api/public/science/articles/statistics\"")
    print()


def frontend_js_example():
    """前端JavaScript使用示例"""
    print("=== 前端JavaScript使用示例 ===\n")

    js_code = """
// 科普文章API前端使用示例
const API_BASE = '/api/public/science';

class ScienceArticleService {
    // 获取文章列表
    static async getArticles(params = {}) {
        const { page = 1, size = 10, keyword = '', author_account = '' } = params;

        const queryParams = new URLSearchParams({
            page: page.toString(),
            size: size.toString()
        });

        if (keyword) queryParams.append('keyword', keyword);
        if (author_account) queryParams.append('author_account', author_account);

        try {
            const response = await fetch(`${API_BASE}/articles?${queryParams}`);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('获取文章列表失败:', error);
            return { success: false, message: '网络请求失败', data: null };
        }
    }

    // 获取文章详情
    static async getArticleDetail(articleId) {
        try {
            const response = await fetch(`${API_BASE}/articles/${articleId}`);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('获取文章详情失败:', error);
            return { success: false, message: '网络请求失败', data: null };
        }
    }

    // 获取统计信息
    static async getStatistics() {
        try {
            const response = await fetch(`${API_BASE}/articles/statistics`);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('获取统计信息失败:', error);
            return { success: false, message: '网络请求失败', data: null };
        }
    }
}

// 使用示例
async function example() {
    // 获取文章列表
    const articles = await ScienceArticleService.getArticles({
        page: 1,
        size: 10,
        keyword: '科学'
    });
    console.log('文章列表:', articles);

    // 获取统计信息
    const stats = await ScienceArticleService.getStatistics();
    console.log('统计信息:', stats);
}
"""

    print(js_code)


if __name__ == "__main__":
    # 显示API信息
    print("科普文章专用API接口信息")
    print("=" * 50)
    print("基础URL: http://localhost:5000/api/public/science")
    print()
    print("可用接口:")
    print("• GET /articles                    - 获取科普文章列表")
    print("• GET /articles/<id>               - 获取科普文章详情")
    print("• GET /articles/statistics         - 获取科普文章统计")
    print()

    # 运行演示
    print("\n" + "=" * 50)
    demo_api_usage()

    print("\n" + "=" * 50)
    curl_commands()

    print("\n" + "=" * 50)
    frontend_js_example()