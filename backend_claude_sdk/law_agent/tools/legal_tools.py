"""法律检索工具模块"""

import json
import os
from typing import Any

import requests

from claude_agent_sdk import tool, create_sdk_mcp_server


@tool("search_law", "通过法律法规数据库检索相关的法律条文、规定或法律文件。支持语义检索，默认返回现行有效的法规。", {"query": str})
async def search_law(args: dict[str, Any]) -> dict[str, Any]:
    """法规检索"""
    query_text = args.get("query", "")
    url = "https://openapi.delilegal.com/api/qa/v3/search/queryListLaw"
    header = {
        "Content-Type": "application/json",
        "appid": os.getenv("DELI_APPID"),
        "secret": os.getenv("DELI_SECRET")
    }
    payload = {
        "pageNo": 1,
        "pageSize": 5,
        "sortField": "correlation",
        "sortOrder": "desc",
        "condition": {
            "keywords": [query_text],
            "fieldName": "semantic",
            "timeLinessTypeArr": ["5"]
        }
    }
    try:
        response = requests.post(url, headers=header, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False, indent=2)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"法规检索错误: {str(e)}"
            }],
            "is_error": True
        }


@tool("search_cases", "类案检索工具。通过输入关键词列表，从法律案例数据库中检索相关的法院判例、裁判文书及其基本信息。支持关联度排序，默认检索各级法院案例。", {"keywords": list})
async def search_cases(args: dict[str, Any]) -> dict[str, Any]:
    """类案检索"""
    keywords = args.get("keywords", [])
    url = "https://openapi.delilegal.com/api/qa/v3/search/queryListCase"
    header = {
        "Content-Type": "application/json",
        "appid": os.getenv("DELI_APPID"),
        "secret": os.getenv("DELI_SECRET")
    }
    payload = {
        "pageNo": 1,
        "pageSize": 3,
        "sortField": "correlation",
        "sortOrder": "desc",
        "condition": {
            "keywordArr": keywords,
            "courtLevelArr": ["0", "1", "2"]
        }
    }
    try:
        response = requests.post(url, headers=header, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False, indent=2)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"类案检索错误: {str(e)}"
            }],
            "is_error": True
        }


LEGAL_TOOLS_SERVER = create_sdk_mcp_server(
    name="legal_tools",
    version="1.0.0",
    tools=[search_law, search_cases]
)
