import { describe, expect, it } from 'vitest';

import { formatStatisticsInputError } from '@views/sec-chat/audit-log-retrieval/utils/statistics-input-error';

describe('统计创建参数错误', () => {
  it('展示 field_name 和 loc/msg', () => {
    const error = {
      message: '附件数据格式错误',
      code: '2908017',
      response: {
        data: {
          result: false,
          code: '2908017',
          message: '附件数据格式错误',
          errors: {
            field_name: 'input_data',
            errors: [
              {
                type: 'value_error',
                loc: ['field', 'raw_name'],
                msg: 'Value error, 不支持的日志根字段，请使用字段目录中的 raw_name；自定义子字段通过 keys 指定',
              },
            ],
          },
        },
      },
    };
    const text = formatStatisticsInputError(error, '创建统计失败');
    expect(text).toBe('input_data：field.raw_name: Value error, 不支持的日志根字段，请使用字段目录中的 raw_name；自定义子字段通过 keys 指定');
  });

  it('没有结构化错误时退回兜底文案', () => {
    expect(formatStatisticsInputError({ message: '网络错误' }, '创建统计失败')).toBe('创建统计失败');
  });
});
