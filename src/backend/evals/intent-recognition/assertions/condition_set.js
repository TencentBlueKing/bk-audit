"use strict";

/**
 * 比较 Agent 业务条件集合是否与期望完全一致。
 *
 * 规范化规则：
 * - 条件集合无序，按出现次数比较，多一条或少一条都不通过。
 * - keys 保持路径顺序，不排序。
 * - filters 按值的多重集比较，顺序无关；数值字段按查询层类型转换后比较。
 * - 非数值字段保留字符串和数字的原始类型，避免把字符串标识符误判为数值。
 * - field_type 只在期望条目显式给出时比较。
 */

const INTEGER_FIELD_TYPES = new Set(["int", "long", "timestamp"]);
const FLOAT_FIELD_TYPES = new Set(["double", "float"]);

function taggedValue(value) {
    if (value === null) {
        return "null";
    }
    return `${typeof value}:${JSON.stringify(value)}`;
}

function normalizedFilterValue(value, fieldType) {
    if (INTEGER_FIELD_TYPES.has(fieldType)) {
        if (typeof value === "number" && Number.isInteger(value)) {
            return `numeric:${BigInt(value).toString()}`;
        }
        if (typeof value === "string" && /^[+-]?\d+$/.test(value)) {
            return `numeric:${BigInt(value).toString()}`;
        }
    }
    if (FLOAT_FIELD_TYPES.has(fieldType)) {
        const numeric = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
        if (Number.isFinite(numeric) && String(value).trim() !== "") {
            return `numeric:${numeric}`;
        }
    }
    return taggedValue(value);
}

function filterSignature(filters, fieldType) {
    return (filters || []).map((value) => normalizedFilterValue(value, fieldType)).sort();
}

function actualField(condition) {
    return condition.field || condition;
}

function signature(condition, includeFieldType, normalizationFieldType) {
    const field = actualField(condition);
    const payload = {
        raw_name: field.raw_name,
        keys: field.keys || [],
        operator: condition.operator,
        filters: filterSignature(condition.filters, normalizationFieldType),
    };
    if (includeFieldType) {
        payload.field_type = field.field_type;
    }
    return JSON.stringify(payload);
}

function matchesCondition(candidate, expected) {
    const candidateField = actualField(candidate);
    const expectedField = actualField(expected);
    const includeFieldType = Object.prototype.hasOwnProperty.call(expectedField, "field_type");
    if (includeFieldType && candidateField.field_type !== expectedField.field_type) {
        return false;
    }
    const normalizationFieldType = expectedField.field_type;
    return (
        signature(candidate, includeFieldType, normalizationFieldType) ===
        signature(expected, includeFieldType, normalizationFieldType)
    );
}

function matchesConditionSet(condition, expectedConditions) {
    const actual = Array.isArray(condition && condition.conditions) ? condition.conditions : [];
    const expected = expectedConditions || [];
    if (actual.length !== expected.length) {
        return false;
    }
    const used = new Set();
    return expected.every((item) => {
        const index = actual.findIndex((candidate, candidateIndex) => {
            return !used.has(candidateIndex) && matchesCondition(candidate, item);
        });
        if (index < 0) {
            return false;
        }
        used.add(index);
        return true;
    });
}

module.exports = {
    matchesConditionSet,
};
