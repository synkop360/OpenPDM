export type AppView =
  | "home"
  | "notifications"
  | "projects"
  | "project"
  | "plugin-administration";

export const projectTabs = [
  "overview",
  "assets",
  "relationships",
  "collaboration",
  "members",
] as const;

export type ProjectTab = (typeof projectTabs)[number];

export type AppRoute = {
  view: AppView;
  projectId: string | null;
  projectTab: ProjectTab;
};

export function parseAppRoute(pathname: string): AppRoute {
  const routeParts = pathname.split("/").filter(Boolean);
  const isProjectRoute = routeParts[0] === "projects" && routeParts.length >= 2;
  const requestedTab = routeParts[2];

  return {
    view:
      routeParts[0] === "administration" && routeParts[1] === "plugins"
        ? "plugin-administration"
        : routeParts[0] === "notifications"
          ? "notifications"
          : routeParts[0] === "projects"
          ? isProjectRoute
            ? "project"
            : "projects"
          : "home",
    projectId: isProjectRoute ? routeParts[1] : null,
    projectTab: projectTabs.includes(requestedTab as ProjectTab)
      ? (requestedTab as ProjectTab)
      : "overview",
  };
}
