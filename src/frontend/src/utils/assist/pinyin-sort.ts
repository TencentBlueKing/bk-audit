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
 * @desc 中文字段名排序器（支持拼音排序）
 */
export const unifiedFieldNameSorter = new Intl.Collator(['zh-Hans-CN-u-co-pinyin', 'en'], {
  sensitivity: 'base',
  numeric: true,
});

/**
 * @desc 拼音首字母边界映射表
 */
export const pinyinInitialBoundaries: readonly (readonly [string, string])[] = [
  ['a', '阿'],
  ['b', '芭'],
  ['c', '擦'],
  ['d', '搭'],
  ['e', '蛾'],
  ['f', '发'],
  ['g', '噶'],
  ['h', '哈'],
  ['j', '击'],
  ['k', '喀'],
  ['l', '垃'],
  ['m', '妈'],
  ['n', '拿'],
  ['o', '哦'],
  ['p', '啪'],
  ['q', '期'],
  ['r', '然'],
  ['s', '撒'],
  ['t', '塌'],
  ['w', '挖'],
  ['x', '昔'],
  ['y', '压'],
  ['z', '匝'],
];

/**
 * @desc 检查是否为 ASCII 字母或数字
 * @param {string} value
 * @returns {boolean}
 */
export const isAsciiAlphaNumeric = (value = ''): boolean => /^[a-z0-9]$/i.test(value);

/**
 * @desc 检查是否为中文字符
 * @param {string} value
 * @returns {boolean}
 */
export const isChineseCharacter = (value = ''): boolean => /^[\u4e00-\u9fff]$/.test(value);

/**
 * @desc 获取中文字符的拼音首字母
 * @param {string} value
 * @returns {string}
 */
export const getPinyinInitial = (value = ''): string => {
  if (!isChineseCharacter(value)) return value.toLowerCase();

  for (let index = pinyinInitialBoundaries.length - 1; index >= 0; index -= 1) {
    const [, boundary] = pinyinInitialBoundaries[index];
    const initial = pinyinInitialBoundaries[index][0];

    if (unifiedFieldNameSorter.compare(value, boundary) >= 0) {
      return initial;
    }
  }

  return value.toLowerCase();
};

/**
 * @desc 转换为统一的排序键（支持中英文混合排序）
 * @param {string} value
 * @returns {string}
 */
export const toUnifiedSortKey = (value = ''): string => Array.from(value.trim().toLowerCase()).map((char) => {
  if (isAsciiAlphaNumeric(char)) return char;
  if (isChineseCharacter(char)) return getPinyinInitial(char);
  return char;
})
  .join('');

/**
 * @desc 比较字段名称（支持中英文混合拼音排序）
 * @param {string} first
 * @param {string} second
 * @returns {number}
 */
export const compareFieldName = (first = '', second = ''): number => {
  const firstKey = toUnifiedSortKey(first);
  const secondKey = toUnifiedSortKey(second);

  if (firstKey !== secondKey) {
    return firstKey.localeCompare(secondKey, 'en', { sensitivity: 'base', numeric: true });
  }

  return unifiedFieldNameSorter.compare(first, second);
};
