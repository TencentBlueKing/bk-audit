# -*- coding: utf-8 -*-
# flake8: noqa
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

# Base
PAGE = 1
PAGE_SIZE = 10

META_QUERY_PARAMS = {
    "share_uid": "just_test",
    "type": "dashboard",
    "xo[tt]": "pp",
}

META_QUERY_PARAMS = {
    "share_uid": "just_test",  # 替换为随机字符
    "type": "dashboard",
    "xo[tt]": "pp",
}
META_QUERY_RESPONSE = {
    "result": True,
    "code": 200,
    "data": {
        "type": "dashboard",
        "data": {
            "id": 14745,
            "created_time": "2024-11-05 11:28:24",
            "updated_time": "2025-03-05 13:34:36",
            "space_uid": "xP5szf3VhtJwkjNz44u1Z7",
            "dashboard_uid": "hDs5B7k8cLhbVpmQm4Y6Jz",
            "dashboard_title": "审计中心风险视图（全风险）",
            "parent_version": "V80",
            "version": "V81",
            "description": "",
            "panels": [
                {
                    "uid": "jx-c1dbe3u3-kh9874fh-q1bsw2fp",
                    "mode": "layout",
                    "type": "row",
                    "query": {
                        "limit": {"size": 1000, "offset": None},
                        "order": [],
                        "where": [],
                        "metrics": [],
                        "is_linked": False,
                        "raw_query": False,
                        "variation": [],
                        "dimensions": [],
                        "drill_down": [],
                        "is_drilled": False,
                        "query_text": "",
                        "link_fields": [],
                        "query_mode": "simple",
                        "time_compare": [],
                        "need_time_compare": False,
                    },
                    "title": "关键指标",
                    "panels": [],
                    "dataset": {"db_type": None, "dataset_uid": "", "datasource_uid": ""},
                    "filters": [],
                    "gridPos": {
                        "h": 3,
                        "i": "jx-c1dbe3u3-kh9874fh-q1bsw2fp",
                        "w": 100,
                        "x": 0,
                        "y": 0,
                        "maxH": 3,
                        "maxW": 100,
                        "minH": 3,
                        "minW": 100,
                        "moved": False,
                    },
                    "build_in": True,
                    "category": "layout",
                    "collapsed": False,
                    "space_uid": "m4cbRz2Gz7hD1Fw9K3P7hQ",
                    "sub_title": "",
                    "chartStyle": {
                        "info": {
                            "title": {"show": True, "align": "start", "color": "#313238"},
                            "sub_title": {"show": False, "align": "start", "color": "#979BA5"},
                            "description": {"show": False, "align": "start", "color": "#ffffff"},
                        },
                        "border": {"color": "#000", "style": "none", "width": 1, "radius": 0},
                        "background": {
                            "url": "",
                            "size": "contain",
                            "color": "#fff",
                            "bgType": "local",
                            "repeat": "no-repeat",
                            "opacity": 30,
                            "localUrl": "",
                            "position": "center",
                            "isShowBgImg": False,
                        },
                    },
                    "description": "",
                    "privateAttrs": {},
                    "dashboard_uid": "tb93m7A2Qh56npz8kgD16m",
                },
                {
                    "uid": "ZweqF42pz6pU17nReBzYT9",
                    "mode": "action",
                    "type": "selector",
                    "query": {
                        "limit": {"size": 1000, "offset": None},
                        "order": [],
                        "where": [],
                        "params": "",
                        "metrics": [],
                        "is_linked": False,
                        "raw_query": False,
                        "variation": [],
                        "dimensions": [],
                        "drill_down": [],
                        "is_drilled": False,
                        "query_mode": "simple",
                        "query_text": "",
                        "link_fields": [],
                        "process_code": "",
                        "time_compare": [],
                        "time_dimensions": {},
                        "need_time_compare": False,
                    },
                    "title": "选择接入系统",
                    "panels": [],
                    "dataset": {"db_type": None, "dataset_uid": "", "datasource_uid": ""},
                    "filters": [],
                    "gridPos": {
                        "h": 7,
                        "i": "ZweqF42pz6pU17nReBzYT9",
                        "w": 25,
                        "x": 0,
                        "y": 0,
                        "maxH": 370,
                        "maxW": 100,
                        "minH": 3,
                        "minW": 8,
                        "moved": False,
                    },
                    "build_in": True,
                    "category": "Action",
                    "collapsed": False,
                    "space_uid": "M9Zd8Ptxy7nF5G7K8uW3q2",
                    "sub_title": "",
                    "chartStyle": {
                        "info": {
                            "title": {"show": True, "align": "start", "color": ""},
                            "sub_title": {"show": False, "align": "start", "color": ""},
                            "description": {"show": False, "align": "start", "color": "#ffffff"},
                        },
                        "border": {
                            "color": "",
                            "style": "none",
                            "width": 1,
                            "radius": 0,
                            "padding": [16, 16, 16, 16],
                            "isCustomPadding": False,
                        },
                        "background": {
                            "url": "",
                            "size": "contain",
                            "color": "",
                            "bgType": "local",
                            "repeat": "no-repeat",
                            "opacity": 30,
                            "localUrl": "",
                            "position": "center",
                            "isShowBgImg": False,
                        },
                    },
                    "chartConfig": {
                        "sql": "",
                        "flag": "system_id",
                        "json": [{"label": "x", "value": "o"}],
                        "type": "table",
                        "field": {
                            "id": 39145,
                            "uid": "Bk56qa6L3tP3oV3s7oF0V7",
                            "name": "id",
                            "type": "string",
                            "table": None,
                            "remark": "",
                            "map_uid": "",
                            "raw_name": "id",
                            "data_type": "dimension",
                            "is_joined": None,
                            "is_virtual": False,
                            "dataset_uid": "b4F67m3vQ0A5lY2I29j7i1",
                            "display_name": "实例ID",
                        },
                        "scope": [
                            {
                                "field": {
                                    "uid": "rP4vcsZkeD38uj1h8Jb49t",
                                    "remark": "",
                                    "map_uid": "",
                                    "aggregate": None,
                                    "is_joined": False,
                                    "is_virtual": False,
                                },
                                "panel_uid": [],
                                "select_all": False,
                                "dataset_uid": "",
                                "datasource_uid": "",
                            }
                        ],
                        "layout": "vertical",
                        "add_all": False,
                        "default": "o",
                        "multiple": False,
                        "dataset_uid": "e2H1MwV7Gk8FZP9uI2y0gL",
                        "defaultType": "specify",
                        "label_field": {
                            "id": 39147,
                            "uid": "sY3k9G6zHb7FfR5c8P1pX9",
                            "name": "display_name",
                            "type": "string",
                            "table": None,
                            "remark": "",
                            "map_uid": "",
                            "raw_name": "display_name",
                            "data_type": "dimension",
                            "is_joined": None,
                            "is_virtual": False,
                            "dataset_uid": "e2H1MwV7Gk8FZP9uI2y0gL",
                            "display_name": "实例名称",
                        },
                        "select_first": False,
                        "datasource_uid": "iD0bW1jP9Q0XfZ8nW4aJ0m",
                        "defaultDynamic": 1,
                    },
                    "description": "选择系统",
                    "privateAttrs": {},
                    "advanceConfig": {},
                    "id": 19760,
                    "created_time": "2025-03-20 20:58:35",
                    "updated_time": "2025-03-20 21:00:37",
                    "dashboard_uid": "tmKp6RyXqb7Zw9Xr1wq1R5",
                    "father_uid": "",
                    "child_panels": [],
                    "dataId": "",
                    "data": {},
                },
            ],
            "colors": {},
            "style": {
                "info": {
                    "title": {"show": True, "align": "start", "color": "#313238"},
                    "sub_title": {"show": False, "align": "start", "color": "#979BA5"},
                    "description": {"show": False, "align": "start", "color": "#ffffff"},
                },
                "border": {"color": "#000", "style": "none", "width": 1, "radius": 0},
                "background": {
                    "url": "",
                    "size": "contain",
                    "color": "#fff",
                    "bgType": "local",
                    "repeat": "no-repeat",
                    "opacity": 30,
                    "localUrl": "",
                    "position": "center",
                    "isShowBgImg": False,
                },
            },
            "variables": [],
            "actionMapPanelRelation": {
                "--aY29tRg92pqFXJHNjLvQe": {
                    "3JMaxL2RPJvnDFwdG3NPFE": {
                        "dtEventTime": {"flag": "dtEventTime", "type": "time-ranger", "value": ["now-7d", "now"]}
                    },
                    "3pnLr3ayoqXecvoH7KJkXa": {"dept_name": {"flag": "dept_name", "type": "selector", "value": ""}},
                    "4R6sIGxga0xMeK6LQy5IUO": {"tag": {"flag": "tag", "type": "selector", "value": ["人员"]}},
                },
                "--NxJrRvmOh74gX8dp7lWz6": {
                    "3JMaxL2RPJvnDFwdG3NPFE": {
                        "dtEventTime": {"flag": "dtEventTime", "type": "time-ranger", "value": ["now-7d", "now"]}
                    },
                    "3pnLr3ayoqXecvoH7KJkXa": {"dept_name": {"flag": "dept_name", "type": "selector", "value": ""}},
                    "4R6sIGxga0xMeK6LQy5IUO": {"tag": {"flag": "tag", "type": "selector", "value": ["人员"]}},
                },
            },
            "panel_links": [],
            "data": {"variables": [], "panel_links": [], "new_pos_version": True},
        },
        "filters": {
            "3JMaxL2RPJvnDFwdG3NPFE": ["now-30d", "now"],
            "4R6sIGxga0xMeK6LQy5IUO": 1,
            "3pnLr3ayoqXecvoH7KJkXa": "",
        },
        "constants": {},
        "panel_plugins": [],
        "datasource_plugins": [],
    },
    "message": None,
    "request_id": "",
    "trace_id": "",
}
CHECK_DATA = [{'name': 'a', 'value': 'A'}]
