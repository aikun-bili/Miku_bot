"""WebUI 启动冒烟测试。

用法：``.venv\\Scripts\\python.exe boot_test.py``

覆盖：401 / 404 拦截、JWT 登录与刷新、参考前端（/next）静态资源、
V1 兼容接口（/miku/api/v1，旧前缀保留别名）、旧版 /api、路径越界、WebSocket、薄入口。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.webui_next import mount
from utils.webui_next.services.auth_service import get_password

PASSED = 0
FAILED = 0
V1 = "/miku/api/v1"


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} {detail}")


def main() -> int:
    print("=" * 60)
    print("MikuBot WebUI 启动冒烟测试（参考前端 /next）")
    print("=" * 60)

    app = FastAPI(title="miku-webui-test")
    check("WebUI 挂载成功", mount(app))
    client = TestClient(app)

    print("\n[1] 路由与拦截")
    check("未知页面返回 404", client.get("/no-such-page").status_code == 404)
    check("V1 未登录返回 401", client.get(f"{V1}/dashboard").status_code == 401)
    check("旧版 /api 未登录返回 401", client.get("/api/dashboard").status_code == 401)

    response = client.get("/", follow_redirects=False)
    check("根路径跳转 /next/", response.status_code in (302, 307), str(response.status_code))
    response = client.get("/dashboard", follow_redirects=False)
    check("旧页面跳转新前端", response.status_code in (302, 307))

    print("\n[2] 参考前端静态资源")
    response = client.get("/next/")
    check("前端首页可访问", response.status_code == 200 and "MikuBot 管理后台" in response.text)
    response = client.get("/next/assets/index-DwfasqRA.js")
    check("前端 JS 可访问", response.status_code == 200, str(response.status_code))
    response = client.get("/next/favicon.ico")
    check("前端图标可访问", response.status_code == 200)
    response = client.get("/next/assets/title-BdxO_BrW.png")
    check("主题标题图可访问", response.status_code == 200)

    print("\n[3] V1 登录与令牌")
    response = client.post(f"{V1}/auth/login", json={"username": "admin", "password": "__wrong__"})
    check("错误密码返回 401", response.status_code == 401, str(response.status_code))

    password = get_password()
    response = client.post(f"{V1}/auth/login", json={"username": "admin", "password": password})
    payload = response.json()
    data = payload.get("data") or {}
    token = data.get("access_token", "")
    check("登录成功", response.status_code == 200 and payload.get("success") is True, response.text[:160])
    check("access_token 是 JWT", token.count(".") == 2)
    check("返回 refresh_token", str(data.get("refresh_token", "")).count(".") == 2)

    raw_headers = {"Authorization": token}
    response = client.get(f"{V1}/system/status", headers=raw_headers)
    check("原始 Authorization 头可用", response.status_code == 200, str(response.status_code))

    response = client.post(f"{V1}/auth/refresh", params={"token": token})
    check("refresh 接口兼容 access token", response.json().get("success") is True, response.text[:160])

    bearer = {"Authorization": f"Bearer {token}"}

    print("\n[4] V1 核心接口字段")
    response = client.get(f"{V1}/dashboard", headers=bearer)
    body = response.json()
    overview = (body.get("data") or {}).get("overview") or {}
    check("仪表盘 overview 完整", {"bot_status", "uptime", "group_count", "friend_count", "plugin_count"} <= set(overview), response.text[:200])
    check("仪表盘 plugin_count 为数字", isinstance(overview.get("plugin_count"), int))

    response = client.get(f"{V1}/system/status", headers=bearer)
    status = response.json().get("data") or {}
    check("系统状态字段", {"cpu", "memory", "disk", "check_time"} <= set(status))

    response = client.get(f"{V1}/system/health", headers=bearer)
    check("健康状态字段", "status" in (response.json().get("data") or {}))

    response = client.get(f"{V1}/main/bot-status/list", headers=bearer)
    check("Bot 状态列表", "current" in (response.json().get("data") or {}))

    response = client.get(f"{V1}/main/chat-statistics", headers=bearer)
    check("聊天统计字段", {"all", "day", "week", "month", "year"} <= set(response.json().get("data") or {}))

    response = client.post(f"{V1}/plugin/list", json={"page": 1, "page_size": 10}, headers=bearer)
    plugin_data = response.json().get("data") or {}
    check("插件列表分页字段", {"items", "total", "page", "page_size", "has_next", "has_prev"} <= set(plugin_data))

    response = client.get(f"{V1}/plugin/config/miku_checkin", headers=bearer)
    config_data = response.json().get("data") or {}
    check("插件配置结构", {"module", "name", "configs"} <= set(config_data))

    response = client.get(f"{V1}/manage/group-list", headers=bearer)
    check("群列表为数组", isinstance(response.json().get("data"), list))
    response = client.get(f"{V1}/manage/friend-list", headers=bearer)
    check("好友列表为数组", isinstance(response.json().get("data"), list))

    response = client.get(f"{V1}/manage/request-list", headers=bearer)
    req = response.json().get("data") or {}
    check("申请列表结构", {"friend", "group"} <= set(req))

    response = client.get(f"{V1}/analytics/trend", headers=bearer)
    trend = response.json().get("data") or {}
    check("趋势数据字段", {"data_points", "total_message_count", "granularity"} <= set(trend))

    response = client.get(f"{V1}/database/tables", headers=bearer)
    check("数据库表列表", isinstance(response.json().get("data"), list))

    response = client.get(f"{V1}/file/list", params={"path": ""}, headers=bearer)
    check("文件列表结构", {"files", "current_path"} <= set(response.json().get("data") or {}))

    response = client.get(f"{V1}/store/get-plugin-store", headers=bearer)
    check("插件商店返回结构", {"install_module", "plugin_list"} <= set(response.json().get("data") or {}))

    print("\n[5] 安全边界")
    response = client.get(f"{V1}/file/list", params={"path": "../../"}, headers=bearer)
    check("路径越界返回 403", response.status_code == 403, str(response.status_code))
    response = client.get(f"{V1}/file/read", params={"file_path": "/etc/passwd"}, headers=bearer)
    check("绝对路径被拒绝", response.status_code in (403, 404), str(response.status_code))

    print("\n[6] WebSocket")
    try:
        with client.websocket_connect("/ws/status") as websocket:
            message = websocket.receive_json()
        check("状态 WebSocket 推送", message.get("type") == "system_status", str(message)[:120])
    except Exception as e:
        check("状态 WebSocket 推送", False, str(e)[:120])

    try:
        with client.websocket_connect("/ws/logs") as websocket:
            message = websocket.receive_json()
        check("日志 WebSocket 连接", message.get("type") == "connected", str(message)[:120])
    except Exception as e:
        check("日志 WebSocket 连接", False, str(e)[:120])

    print("\n[7] 薄入口与生命周期")
    import utils.webui_new as entry

    check("薄入口暴露挂载函数", callable(getattr(entry, "_mount_admin", None)))
    check("薄入口暴露监听健康检查", callable(getattr(entry, "_start_listener_healthcheck", None)))
    check("薄入口暴露关闭回调", callable(getattr(entry, "_stop_listener_healthcheck", None)))

    print("\n" + "=" * 60)
    print(f"结果：{PASSED} 通过，{FAILED} 失败")
    print("=" * 60)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
