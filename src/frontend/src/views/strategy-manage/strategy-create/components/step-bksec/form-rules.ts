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

export const DEFAULT_BKSEC_OPERATOR = '{{ risk.operator }}';

export interface DynamicFieldSegment {
  value: string;
  isVariable: boolean;
}

const VARIABLE_CANDIDATE_RE = /\{\{([^{}]*)}}/g;

export const parseDynamicFieldValue = (value: string): DynamicFieldSegment[] => {
  const source = String(value || '');
  if (!source) return [];
  const segments: DynamicFieldSegment[] = [];
  let cursor = 0;
  source.replace(VARIABLE_CANDIDATE_RE, (token, expression: string, offset: number) => {
    const surroundedByExtraBraces = source[offset - 1] === '{'
      || source[offset + token.length] === '}';
    if (!expression.trim() || surroundedByExtraBraces) {
      return token;
    }
    if (offset > cursor) {
      segments.push({ value: source.slice(cursor, offset), isVariable: false });
    }
    segments.push({ value: token, isVariable: true });
    cursor = offset + token.length;
    return token;
  });
  if (cursor < source.length) {
    segments.push({ value: source.slice(cursor), isVariable: false });
  }
  return segments.length ? segments : [{ value: source, isVariable: false }];
};

export const insertDynamicFieldToken = (
  value: string,
  token: string,
  caret: number,
) => {
  const source = String(value || '');
  const position = Math.max(0, Math.min(caret, source.length));
  return {
    value: `${source.slice(0, position)}${token}${source.slice(position)}`,
    caret: position + token.length,
  };
};

export interface BksecFormField {
  id: string;
  name: string;
  required: boolean;
}

export const retainFieldValues = (
  previous: Record<string, string>,
  fields: BksecFormField[],
) => {
  const next: Record<string, string> = {};
  fields.forEach((field) => {
    if (previous[field.id]) next[field.id] = previous[field.id];
  });
  if (!next.operator) next.operator = DEFAULT_BKSEC_OPERATOR;
  return next;
};

export const missingRequiredFields = <T extends BksecFormField>(
  fields: T[],
  values: Record<string, string>,
): T[] => fields.filter(field => field.required && !String(values[field.id] || '').trim());

export const shouldValidateBksec = (action: 'submit' | 'draft') => action === 'submit';

export const shouldRequestRemotePreview = (isCreate: boolean, riskId?: string) => (
  !isCreate && !!riskId
);

export const canSendTestTicket = (riskId?: string) => !!String(riskId || '').trim();
