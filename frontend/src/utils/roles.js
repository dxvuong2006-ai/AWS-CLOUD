export function homeForRole(role) {
  if (role === "INSTRUCTOR") return "/instructor/dashboard";
  if (role === "TEACHER") return "/instructor/dashboard";
  if (role === "ADMIN") return "/admin/users";
  return "/courses";
}

export function isAllowedRole(role, roles) {
  const normalized = role === "TEACHER" ? "INSTRUCTOR" : role;
  const normalizedRoles = roles?.map(item => item === "TEACHER" ? "INSTRUCTOR" : item);
  return ["STUDENT", "INSTRUCTOR", "ADMIN"].includes(normalized) &&
    (!normalizedRoles || normalizedRoles.includes(normalized));
}
