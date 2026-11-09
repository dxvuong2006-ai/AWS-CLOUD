const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "../src/utils/courseFilters.js"), "utf8");
const api = import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const courses = [{id: 1, title: "Cloud cơ bản"}, {id: "2", title: "Cloud nâng cao"}, {id: "3", title: "Python"}];

test("three filters partition the catalog, including numeric course IDs", async () => {
  const {filterCourses} = await api;
  const ids = new Set(["1", "3"]);
  assert.deepEqual(filterCourses(courses, "", "all", ids), courses);
  assert.deepEqual(filterCourses(courses, "", "enrolled", ids), [courses[0], courses[2]]);
  assert.deepEqual(filterCourses(courses, "", "not-enrolled", ids), [courses[1]]);
});
test("search is combined with enrollment and survives filter changes", async () => {
  const {filterCourses} = await api;
  const ids = new Set(["1"]);
  assert.deepEqual(filterCourses(courses, " CLOUD ", "enrolled", ids), [courses[0]]);
  assert.deepEqual(filterCourses(courses, " CLOUD ", "not-enrolled", ids), [courses[1]]);
  assert.deepEqual(filterCourses(courses, " CLOUD ", "all", ids), courses.slice(0, 2));
  assert.deepEqual(filterCourses(courses, "Python", "enrolled", ids), []);
});
test("empty and fully enrolled accounts return the correct empty states", async () => {
  const {filterCourses} = await api;
  assert.deepEqual(filterCourses(courses, "", "enrolled", new Set()), []);
  assert.deepEqual(filterCourses(courses, "", "not-enrolled", new Set()), courses);
  assert.deepEqual(filterCourses(courses, "", "not-enrolled", new Set(["1","2","3"])), []);
  assert.deepEqual(filterCourses([], "", "all", new Set()), []);
});