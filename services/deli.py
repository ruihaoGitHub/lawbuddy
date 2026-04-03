import httpx
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ==============================
# 得理官方 API 配置（和你给的示例完全一致）
# ==============================
DELI_BASE_URL = "https://openapi.delilegal.com/api/qa/v3"
DELI_APPID = "QthdBErlyaYvyXul"       # 官方示例 appid
DELI_SECRET = "EC5D455E6BD348CE8E18BE05926D2EBE"  # 官方示例 secret
TIMEOUT = 60


class DeliAPIClient:
    """【官方对齐版】得理法律 API 客户端（同步版）"""

    def __init__(self, appid: str = None, secret: str = None):
        self.appid = appid or DELI_APPID
        self.secret = secret or DELI_SECRET
        self.headers = {
            "appid": self.appid,
            "secret": self.secret,
            "Content-Type": "application/json"
        }
        # 同步 HTTP 客户端
        self.client = httpx.Client(timeout=httpx.Timeout(TIMEOUT))

    # -------------------------------------------------------------------------
    # 【官方接口】案例检索 queryListCase
    # -------------------------------------------------------------------------
    def query_list_case(
        self,
        page_no: int = 1,
        page_size: int = 3,
        sort_field: str = "correlation",
        sort_order: str = "desc",
        condition: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        得理官方案例检索接口
        完全对齐你给的 curl 示例
        """
        url = f"{DELI_BASE_URL}/search/queryListCase"

        # 默认条件（和示例一致）
        if condition is None:
            condition = {
                "caseYearStart": "2020-08-05",
                "caseYearEnd": "2023-08-13",
                "courtLevelArr": ["0"],
                "keywordArr": ["上班途中车祸工伤案例"]
            }

        payload = {
            "pageNo": page_no,
            "pageSize": page_size,
            "sortField": sort_field,
            "sortOrder": sort_order,
            "condition": condition
        }

        try:
            response = self.client.post(
                url=url,
                headers=self.headers,
                json=payload
            )

            if response.status_code != 200:
                logger.error(f"得理API错误 {response.status_code}: {response.text}")
                return {"error": f"API错误 {response.status_code}"}

            return response.json()

        except Exception as e:
            logger.error(f"请求异常: {str(e)}")
            return {"error": str(e)}

    # -------------------------------------------------------------------------
    # 你可以在这里继续加其他官方接口（比如法条检索等）
    # -------------------------------------------------------------------------

    def close(self):
        """关闭客户端"""
        self.client.close()
if __name__ == "__main__":
    # 测试示例
    deli = DeliAPIClient()
    result = deli.query_list_case(
    page_no=1, 
    page_size=3, 
    condition={
        "caseYearStart": "2025-01-05",
        "caseYearEnd": "2025-08-13",
        "courtLevelArr": ["3"],
        "keywordArr": ["拖欠工资"]
    }
    )
    print(result)
    deli.close()