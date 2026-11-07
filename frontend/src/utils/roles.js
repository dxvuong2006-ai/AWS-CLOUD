export function homeForRole(role) {
  if (role === "INSTRUCTOR") return "/instructor/dashboard";
  if (role === "ADMIN") return "/admin/users";
  return "/courses";
}

export function isAllowedRole(role, roles) {
  return ["STUDENT", "INSTRUCTOR", "ADMIN"].includes(role) &&
    (!roles || roles.includes(role));
}
