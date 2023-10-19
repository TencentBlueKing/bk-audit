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
import yamljs from 'yamljs';

/**
 * 校验一个配置项
 */
function validateProperty(property: any) {
  const { length } = property;
  let keyLen = 0;
  let valueStart = length;
  let hasSep = false;
  let precedingBackslash = false;
  let c;
  // 解析 key
  while (keyLen < length) {
    c = property[keyLen];
    if ((c === '=' || c === ':') && !precedingBackslash) {
      valueStart = keyLen + 1;
      hasSep = true;
      break;
    }

    if ((c === ' ' || c === '\t' || c === '\f') && !precedingBackslash) {
      valueStart = keyLen + 1;
      break;
    }

    if (c === '\\') {
      precedingBackslash = !precedingBackslash;
    } else {
      precedingBackslash = false;
    }
    keyLen += 1;
  }
  // 解析 value
  while (valueStart < length) {
    c = property[valueStart];
    if (c !== ' ' && c !== '\t' && c !== '\f') {
      if (!hasSep && (c === '=' || c === ':')) {
        hasSep = true;
      } else {
        break;
      }
    }
    valueStart += 1;
  }

  return (
    validateKeyOrValueForProperty(property, 0, keyLen)
    && validateKeyOrValueForProperty(property, valueStart, length)
  );
}

function validateKeyOrValueForProperty(property: any, start: number, end: number) {
  // check null
  if (start >= end) {
    return false;
  }
  let index = 0;
  let c;
  while (index < property.length) {
    c = property[index += 1];
    if (c !== '\\') {
      continue;
    }

    c = property[index += 1];
    // check backslash
    if (!isPropertyEscape(c)) {
      return false;
    }

    // check Unicode
    if (c === 'u') {
      const unicode = property.slice(index, index + 4).join('');
      if (unicode.match(/^[a-f0-9]{4}$/i) === null) {
        return false;
      }
      index += 4;
    }
  }

  return true;
}

function isPropertyEscape(c = '') {
  return 'abfnrt\\"\'0! #:=u'.includes(c);
}

export default {
  /**
   * 检测json是否合法
   */
  validateJson(str: any) {
    try {
      return !!JSON.parse(str);
    } catch (e) {
      return false;
    }
  },

  /**
   * 检测xml和html是否合法
   */
  // validateXml(str) {
  //   try {
  //     if (typeof DOMParser !== 'undefined') {
  //       const parserObj =          new window.DOMParser()
  //         .parseFromString(str, 'application/xml')
  //         .getElementsByTagName('parsererror') || {};
  //       return parserObj.length === 0;
  //     } if (typeof window.ActiveXObject !== 'undefined') {
  //       const xml = new window.ActiveXObject('Microsoft.XMLDOM');
  //       xml.async = 'false';
  //       xml.loadXML(str);
  //       return xml;
  //     }
  //   } catch (e) {
  //     return false;
  //   }
  // },

  /**
   * 检测yaml是否合法
   */
  validateYaml(str: string) {
    try {
      return yamljs.parse(str);
    } catch (e) {
      return false;
    }
  },

  /**
   * 检测属性是否正确
   */
  validateProperties(str = '') {
    let isNewLine = true;
    let isCommentLine = false;
    let isSkipWhiteSpace = true;
    let precedingBackslash = false;
    let appendedLineBegin = false;
    let skipLF = false;
    let hasProperty = false;
    let property = [];
    for (let i = 0; i < str.length; i++) {
      const c = str[i];

      if (skipLF) {
        skipLF = false;
        if (c === '\n') {
          continue;
        }
      }
      // 跳过行首空白字符
      if (isSkipWhiteSpace) {
        if (c === ' ' || c === '\t' || c === '\f') {
          continue;
        }
        if (!appendedLineBegin && (c === '\r' || c === '\n')) {
          continue;
        }
        appendedLineBegin = false;
        isSkipWhiteSpace = false;
      }

      // 判断注释行
      if (isNewLine) {
        isNewLine = false;
        if (c === '#' || c === '!') {
          isCommentLine = true;
          continue;
        }
      }

      if (c !== '\n' && c !== '\r') {
        property.push(c);
        if (c === '\\') {
          precedingBackslash = !precedingBackslash;
        } else {
          precedingBackslash = false;
        }
        continue;
      }

      // 跳过注释行
      if (isCommentLine || property.length === 0) {
        isNewLine = true;
        isCommentLine = false;
        isSkipWhiteSpace = true;
        property = [];
        continue;
      }

      // 处理转移字符
      if (precedingBackslash) {
        property.pop();
        precedingBackslash = false;
        isSkipWhiteSpace = true;
        appendedLineBegin = true;
        if (c === '\r') {
          skipLF = true;
        }
        continue;
      }
      // 解析出配置项
      // 进行校验
      if (!validateProperty(property)) {
        return false;
      }
      hasProperty = true;
      property = [];
      isNewLine = true;
      isSkipWhiteSpace = true;
    }

    // 校验最后一行
    if (property.length > 0 && !isCommentLine) {
      return validateProperty(property);
    }

    return hasProperty;
  },

  /**
   * 根据类型验证类型
   */
  validate({ content, type }:{content: any, type: string}) {
    const validateObj = {
      json: this.validateJson,
      // xml: this.validateXml,
      // 'text/html': this.validateXml,
      // html: this.validateXml,
      properties: this.validateProperties,
      yaml: this.validateYaml,
    };

    if (!validateObj[type as keyof typeof validateObj]) {
      return true;
    }

    return validateObj[type as keyof typeof validateObj](content);
  },
};
