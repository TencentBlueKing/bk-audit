"use strict";

const { matchesConditionSet } = require("./condition_set");

module.exports = (output, context) => {
    let parsed;
    try {
        parsed = typeof output === "string" ? JSON.parse(output) : output;
    } catch (error) {
        return { pass: false, score: 0, reason: "output is not json" };
    }
    const expected = context && context.vars ? context.vars.expected_conditions : undefined;
    if (!Array.isArray(expected)) {
        return { pass: false, score: 0, reason: "expected_conditions is required" };
    }
    const pass = matchesConditionSet(parsed.condition, expected);
    return {
        pass,
        score: pass ? 1 : 0,
        reason: pass ? "" : "condition set does not match the complete expected collection",
    };
};
