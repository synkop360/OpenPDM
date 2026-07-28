import { projectTabs, type ProjectTab } from "../../app/routes";

const labels: Record<ProjectTab, string> = {
  overview: "Overview",
  assets: "Assets",
  relationships: "Relationships",
  collaboration: "Collaboration",
  members: "Members",
};

type ProjectTabsProps = {
  onValueChange: (value: ProjectTab) => void;
  value: ProjectTab;
};

export function ProjectTabs({ onValueChange, value }: ProjectTabsProps) {
  return (
    <nav aria-label="Project sections" className="project-tabs">
      {projectTabs.map((tab) => (
        <button
          aria-current={tab === value ? "page" : undefined}
          className={tab === value ? "project-tab is-active" : "project-tab"}
          key={tab}
          onClick={() => {
            if (tab !== value) onValueChange(tab);
          }}
          type="button"
        >
          {labels[tab]}
        </button>
      ))}
    </nav>
  );
}
