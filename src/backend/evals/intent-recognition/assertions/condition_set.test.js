"use strict";

const assert = require("assert");
const { matchesConditionSet } = require("./condition_set");

const username = {
    field: { raw_name: "username", keys: [], field_type: "string" },
    operator: "eq",
    filters: ["eval_user_nested"],
};
const extension = {
    field: { raw_name: "extend_data", keys: ["_request_url", "scope_id"], field_type: "string" },
    operator: "eq",
    filters: ["49"],
};
const resultCode = {
    field: { raw_name: "result_code", keys: [], field_type: "int" },
    operator: "include",
    filters: [-1],
};
const expected = [
    { raw_name: "extend_data", keys: ["_request_url", "scope_id"], operator: "eq", filters: ["49"] },
    { raw_name: "username", operator: "eq", filters: ["eval_user_nested"] },
];
const expectedFailure = [
    { raw_name: "result_code", keys: [], field_type: "int", operator: "include", filters: [-1] },
];

assert.strictEqual(
    matchesConditionSet({ conditions: [resultCode] }, expectedFailure),
    true,
    "整型 result_code 的 -1 应与数值型期望一致",
);
assert.strictEqual(
    matchesConditionSet({ conditions: [resultCode] }, [{ ...expectedFailure[0], filters: ["-1"] }]),
    true,
    "整型字段的数值字符串应按查询层类型转换后比较",
);

assert.strictEqual(
    matchesConditionSet({ conditions: [extension, username] }, expected),
    true,
    "username + extend_data 的完整集合应通过，且不受条件顺序影响",
);
assert.strictEqual(
    matchesConditionSet({ conditions: [username, extension, resultCode] }, expected),
    false,
    "多出合法的 result_code 也不能通过",
);
assert.strictEqual(
    matchesConditionSet(
        { conditions: [{ ...extension, field: { ...extension.field, keys: ["scope_id", "_request_url"] } }, username] },
        expected,
    ),
    false,
    "嵌套 keys 顺序不同不能通过",
);
assert.strictEqual(
    matchesConditionSet(
        { conditions: [username, { ...extension, filters: [49] }] },
        expected,
    ),
    false,
    "字符串 ID 49 与数字 49 不是同一条件",
);
assert.strictEqual(
    matchesConditionSet(
        {
            conditions: [
                username,
                {
                    ...extension,
                    field: { ...extension.field, field_type: "int" },
                    filters: [49],
                },
            ],
        },
        expected,
    ),
    false,
    "期望未声明数值类型时不能采用 Agent 输出类型归一字符串标识符",
);
assert.strictEqual(
    matchesConditionSet(
        {
            conditions: [
                username,
                { ...extension, field: { ...extension.field, field_type: "int" } },
            ],
        },
        expected,
    ),
    true,
    "期望未声明 field_type 时不比较类型",
);
assert.strictEqual(
    matchesConditionSet(
        { conditions: [username, extension] },
        expected.map((item) => (item.raw_name === "extend_data" ? { ...item, field_type: "string" } : item)),
    ),
    true,
    "期望声明 field_type 时按声明比较",
);
assert.strictEqual(
    matchesConditionSet(
        { conditions: [username, { ...extension, field: { ...extension.field, field_type: "int" } }] },
        expected.map((item) => (item.raw_name === "extend_data" ? { ...item, field_type: "string" } : item)),
    ),
    false,
    "期望声明的 field_type 不一致时失败",
);

console.log("condition_set assertions passed");
