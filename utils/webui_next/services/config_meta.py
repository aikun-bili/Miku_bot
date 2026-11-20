"""插件 / 配置节的中文元信息（label、description、hint）。

这些内容属于纯展示数据，与具体实现解耦，便于配置页统一渲染。
"""

from typing import Dict

SECTION_META: Dict[str, Dict[str, str]] = {
    "bot": {
        "label": "主配置（bot）",
        "description": "Bot核心参数：超级用户、密码、日志、端口等",
        "has_toggle": False,
    },
    "miku_admin": {"label": "管理员", "description": "重启、刷新配置等管理员指令"},
    "miku_basic": {"label": "基础信息", "description": "Bot 名称、运行状态显示"},
    "miku_weather": {"label": "天气查询", "description": "和风天气 API 配置"},
    "miku_checkin": {"label": "签到", "description": "每日签到奖励设置"},
    "miku_profile": {"label": "个人资料", "description": "个人资料卡片配置"},
    "miku_ai": {"label": "AI 对话", "description": "AI 对话参数及人格提示词"},
    "miku_menu": {"label": "菜单", "description": "菜单展示配置"},
    "miku_notify_admin": {"label": "通知管理员", "description": "将消息转达给管理员"},
    "miku_blacklist": {
        "label": "黑名单拦截",
        "description": "消息黑名单拦截，阻止黑名单用户/群组触发插件",
    },
    "cache_cleanup": {"label": "缓存清理", "description": "自动清理缓存文件设置"},
}

CONFIG_LABELS: Dict[str, Dict[str, Dict[str, str]]] = {
    "bot": {
        "superusers": {"label": "超级用户(QQ号)", "hint": "拥有所有权限的用户QQ号列表，支持多个，修改后需要重启Bot"},
        "webui_password": {"label": "WebUI密码", "hint": "WebUI管理后台登录密码，支持英文数字及标点"},
        "log_level": {"label": "日志等级", "hint": "TRACE / DEBUG / INFO / WARNING / ERROR，级别越高越简洁"},
        "log_to_file": {"label": "日志写入文件", "hint": "true=同时写入文件与终端；false=仅显示在终端"},
        "log_rotation": {"label": "日志滚动周期", "hint": "多久生成一个新日志文件，格式如1 day / 10 MB / 00:00"},
        "log_retention": {"label": "日志保留天数", "hint": "自动清理多少天前的日志文件，超过此天数自动删除"},
        "nickname": {"label": "Bot昵称", "hint": "Bot的简称/昵称，插件中会被触发使用这些昵称的消息"},
        "host": {"label": "监听地址", "hint": "127.0.0.1仅本机访问；0.0.0.0允许所有网络访问"},
        "port": {"label": "监听端口", "hint": "管理后台服务端口（如3108），需要重启才会变生效"},
    },
    "miku_admin": {
        "notify_on_start": {"label": "启动通知", "hint": "true=Bot启动时私聊通知超级用户；false=不通知"},
        "enabled": {"label": "启用", "hint": "true=启用管理员指令功能；false=禁用本插件"},
        "admin_commands": {"label": "管理员指令", "hint": "管理员可触发的指令列表，如重启、配置检查、刷新配置"},
    },
    "miku_basic": {
        "enabled": {"label": "启用", "hint": "true=启用基础信息插件；false=禁用该插件功能"},
        "bot_name": {"label": "Bot名称", "hint": "Bot显示名称，在信息卡片上显示的Bot名"},
        "show_system_info": {"label": "显示系统信息", "hint": "true=信息卡片显示运行时间/系统信息；false=不显示"},
        "response_style": {"label": "响应风格", "hint": "card=生成图片卡片；text=纯文本"},
    },
    "miku_weather": {
        "enabled": {"label": "启用", "hint": "true=启用天气查询插件；false=禁用"},
        "API_KEY": {"label": "API Key", "hint": "和风天气API Key，登录console.qweather.com申请"},
        "DEFAULT_CITY": {"label": "默认城市", "hint": "未指定城市时的查询城市名称"},
        "API_HOST": {"label": "API Host", "hint": "和风天气专属Host，从开发者控制台复制，形如 xxx.re.qweatherapi.com"},
        "GEO_API_HOST": {"label": "GeoAPI Host", "hint": "城市名转地理位置ID的API域名，默认geoapi.qweather.com"},
        "lang": {"label": "语言", "hint": "zh=中文，en=英文，天气描述语言"},
        "response_style": {"label": "响应风格", "hint": "card=生成图片卡片；text=纯文本"},
    },
    "miku_checkin": {
        "enabled": {"label": "启用", "hint": "true=启用签到插件；false=禁用"},
        "response_style": {"label": "响应风格", "hint": "card=生成图片卡片；text=纯文本"},
        "coins_min": {"label": "金币最小值", "hint": "签到获得的金币范围最小值，0或正整数"},
        "coins_max": {"label": "金币最大值", "hint": "签到获得的金币范围最大值"},
        "favor_min": {"label": "好感度最小值", "hint": "签到获得的好感度范围最小值，支持小数"},
        "favor_max": {"label": "好感度最大值", "hint": "签到获得的好感度范围最大值"},
        "double_favor_prob": {"label": "双倍好感概率", "hint": "触发双倍好感的概率(0-1)，例如0.03 = 3%"},
        "card_width": {"label": "卡片宽度", "hint": "图片卡片像素宽度，仅card风格生效"},
        "card_height": {"label": "卡片高度", "hint": "图片卡片像素高度"},
    },
    "miku_profile": {
        "enabled": {"label": "启用", "hint": "true=启用个人资料插件；false=禁用"},
        "response_style": {"label": "响应风格", "hint": "card=生成图片卡片；text=纯文本"},
        "card_width": {"label": "卡片宽度", "hint": "资料卡片宽度，仅card生效"},
        "card_height": {"label": "卡片高度", "hint": "资料卡片高度，0=自适应高度"},
    },
    "miku_ai": {
        "enabled": {"label": "启用", "hint": "true=启用AI对话插件；false=禁用"},
        "response_style": {"label": "响应风格", "hint": "card=生成图片卡片；text=纯文本"},
        "group_reply_on_mention": {"label": "群聊@回复", "hint": "true=群聊中@Bot或提到Bot时自动回复"},
        "group_random_reply_percent": {"label": "群聊随机回复概率", "hint": "群聊中无@时的随机回复概率(0-100)，单位为%"},
        "private_reply_every": {"label": "单聊全部回复", "hint": "true=私聊每条消息都回复；false=不主动回复"},
        "group_history_max": {"label": "群聊历史上限", "hint": "群聊最大保存的历史消息数，AI会携带这些消息做上下文"},
        "private_history_max": {"label": "私聊历史上限", "hint": "私聊最大保存的历史消息数"},
        "history_file": {"label": "历史记录文件", "hint": "聊天记录持久化文件路径，相对项目根目录"},
        "favor_change_probability": {"label": "好感变化概率", "hint": "聊天触发好感度变化的概率(0-100)，单位为%"},
        "favor_increase_min": {"label": "好感增加最小值", "hint": "好感度增加范围最小值，随机浮点数"},
        "favor_increase_max": {"label": "好感增加最大值", "hint": "好感度增加范围最大值"},
        "favor_decrease_min": {"label": "好感减少最小值", "hint": "好感度减少范围最小值"},
        "favor_decrease_max": {"label": "好感减少最大值", "hint": "好感度减少范围最大值"},
        "personality_file": {"label": "人格文件", "hint": "AI人格提示词文件路径，相对项目根"},
        "personality_reload": {"label": "人格热更新", "hint": "true=每次回复重新读取人格文件，方便调试；false=只加载一次"},
        "web_search_enabled": {"label": "联网搜索", "hint": "联网搜索总开关：true=允许联网搜索并注入结果；false=完全关闭联网搜索"},
        "web_search_keyword_only": {"label": "命中关键字", "hint": "true=只有命中关键词（天气/新闻/最新/搜一下等）才搜索；false=由AI结合上下文自主判断是否需要联网搜索"},
        "web_search_max_results": {"label": "搜索结果条数", "hint": "每次联网搜索最多注入的结果条数"},
        "web_search_timeout": {"label": "搜索超时", "hint": "单个搜索引擎的超时时间（秒），超时后自动切换下一个引擎"},
        "temperature": {"label": "采样温度", "hint": "AI回答的创造性，值越高回答越随机(0-2)"},
        "max_tokens": {"label": "最大Token数", "hint": "单次回复最大token数，留空不限"},
        "request_timeout": {"label": "请求超时", "hint": "API请求超时秒数，超过则报错"},
        "vision_enabled": {"label": "启用识图", "hint": "true=启用图片理解功能，需要模型支持vision"},
        "card_width": {"label": "卡片宽度", "hint": "图片卡片像素宽度"},
        "card_height": {"label": "卡片高度", "hint": "图片卡片像素高度，0=自适应"},
    },
    "miku_menu": {
        "enabled": {"label": "启用", "hint": "true=启用菜单插件；false=禁用"},
        "response_style": {"label": "响应风格", "hint": "card=生成图片卡片；text=纯文本"},
        "card_width": {"label": "菜单卡片像素宽度", "hint": "菜单卡片像素宽度"},
        "card_height": {"label": "卡片高度", "hint": "菜单卡片像素高度"},
        "show_icons": {"label": "显示图标", "hint": "true=菜单显示各插件图标；false=仅文字"},
    },
    "cache_cleanup": {
        "enabled": {"label": "启用", "hint": "true=启用缓存自动清理；false=不清理"},
        "cleanup_times": {"label": "清理时间", "hint": "每日自动清理的时间点，24小时制，可多个如00:00, 06:00"},
        "cache_dirs": {"label": "缓存目录", "hint": "要清理的缓存目录列表，相对项目根"},
        "max_age_hours": {"label": "最长保留小时", "hint": "缓存文件最大保留小时数，0=每次全部清理"},
        "file_extensions": {"label": "文件扩展名", "hint": "要清理的文件扩展名列表，如.png.jpg"},
        "verbose": {"label": "详细日志", "hint": "true=日志中显示清理详情；false=仅显示是否清理"},
    },
    "miku_notify_admin": {
        "enabled": {"label": "启用", "hint": "true=启用通知管理员；false=禁用"},
    },
}


def get_label(section: str, key: str) -> str:
    item = CONFIG_LABELS.get(section, {}).get(key, {})
    if isinstance(item, dict):
        return item.get("label", key)
    return item if isinstance(item, str) else key


def get_hint(section: str, key: str) -> str:
    item = CONFIG_LABELS.get(section, {}).get(key, {})
    return item.get("hint", "") if isinstance(item, dict) else ""


def get_section_label(section: str) -> str:
    return SECTION_META.get(section, {}).get("label", section)


def get_section_description(section: str) -> str:
    return SECTION_META.get(section, {}).get("description", section)
