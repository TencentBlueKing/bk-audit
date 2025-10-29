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
/* eslint-env node */
require('@rushstack/eslint-patch/modern-module-resolution');

module.exports = {
  root: true,
  extends: [
    'eslint-config-tencent',
    'plugin:vue/vue3-recommended',
    'eslint:recommended',
    '@vue/eslint-config-typescript/recommended',
  ],
  env: {
    'vue/setup-compiler-macros': true,
  },
  plugins: [
    'simple-import-sort',
  ],
  globals: {
    ValueOf: true,
  },
  rules: {
    '@typescript-eslint/no-explicit-any': 'off',
    'no-param-reassign': ['error'],
    // 对象写在一行时，大括号里需要空格
    // 'object-curly-spacing': ['error', 'always'],
    'simple-import-sort/exports': 'error',
    'simple-import-sort/imports': ['error', {
      groups: [
        ['^[a-zA-Z]'],
        ['^@lib'],
        ['^@service'],
        ['^@model'],
        ['^@hooks'],
        ['^@components'],
        ['^@views'],
        ['^@\\w'],
        ['^@router'],
        ['^@utils'],
        ['^@css'],
        ['^@language'],
        ['^\\.\\.'],
        ['^\\.'],
      ],
    }],
    'import/newline-after-import': 'error',
  },
  overrides: [
    {
      files: ['*.vue'],
      rules: {
        indent: 'off',
        'import/first': 'off',
        'vue/html-closing-bracket-newline': ['error', {
          singleline: 'never',
          multiline: 'never',
        }],
        'vue/attributes-order': ['error', {
          order: [
            'DEFINITION',
            'LIST_RENDERING',
            'CONDITIONALS',
            'RENDER_MODIFIERS',
            'GLOBAL',
            ['UNIQUE', 'SLOT'],
            'TWO_WAY_BINDING',
            'OTHER_DIRECTIVES',
            'OTHER_ATTR',
            'EVENTS',
            'CONTENT',
          ],
          alphabetical: true,
        }],
        'vue/define-macros-order': ['error', {
          order: ['defineProps', 'defineEmits'],
        }],
        'vue/no-undef-properties': ['error', {
          ignores: ['/^\\$/', '/^v-bind\\(/'],
        }],
        'vue/no-unused-properties': ['error', {
          groups: ['props'],
          deepData: false,
          ignorePublicMembers: false,
        }],
        'vue/no-useless-mustaches': ['error', {
          ignoreIncludesComment: false,
          ignoreStringEscape: false,
        }],
        'vue/no-useless-v-bind': ['error', {
          ignoreIncludesComment: false,
          ignoreStringEscape: false,
        }],
        'vue/prefer-separate-static-class': 'error',
        'vue/prefer-true-attribute-shorthand': 'error',
        'vue/script-indent': ['error', 2, {
          baseIndent: 1,
        }],
        'vue/component-name-in-template-casing': ['error', 'kebab-case', {
          registeredComponentsOnly: false,
          ignores: [],
        }],
        'vue/multi-word-component-names': 'off',
      },
    },
  ],
};
