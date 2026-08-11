/*
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
*/

/**
 * 工具侧栏快捷筛选用的虚拟标签（非真实业务标签）
 * -3 全部工具 / -4 我创建的 / -5 最近使用 / -6 我的收藏
 */
export const VIRTUAL_TOOL_TAG_IDS = ['-3', '-4', '-5', '-6'] as const;

/** 虚拟标签名称（含可能被写入 Tag 表的同名脏数据） */
export const VIRTUAL_TOOL_TAG_NAMES = ['全部工具', '我创建的', '最近使用', '我的收藏'] as const;

type TagLike = {
  tag_id?: string | number;
  tag_name?: string;
  id?: string | number;
  name?: string;
};

export const isVirtualToolTag = (tag: TagLike): boolean => {
  const id = String(tag.tag_id ?? tag.id ?? '');
  const name = String(tag.tag_name ?? tag.name ?? '');
  return (VIRTUAL_TOOL_TAG_IDS as readonly string[]).includes(id)
    || (VIRTUAL_TOOL_TAG_NAMES as readonly string[]).includes(name);
};

/** 过滤虚拟/系统快捷标签，保留真实业务标签（含无标签 -2） */
export const filterVirtualToolTags = <T extends TagLike>(tags: T[] = []): T[] => (
  tags.filter(tag => !isVirtualToolTag(tag))
);
