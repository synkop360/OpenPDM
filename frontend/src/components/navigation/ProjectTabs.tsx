import * as Tabs from "@radix-ui/react-tabs";
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
    <Tabs.Root value={value} onValueChange={(next) => onValueChange(next as ProjectTab)}>
      <Tabs.List aria-label="Project sections" className="project-tabs">
        {projectTabs.map((tab) => (
          <Tabs.Trigger
            className="project-tab"
            key={tab}
            onClick={() => {
              if (tab !== value) onValueChange(tab);
            }}
            value={tab}
          >
            {labels[tab]}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
    </Tabs.Root>
  );
}
