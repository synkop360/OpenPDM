import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";

export type MenuItem = {
  disabled?: boolean;
  label: string;
  onSelect: () => void;
};

type ActionMenuProps = {
  items: MenuItem[];
  label: string;
  trigger: ReactNode;
};

export function ActionMenu({ items, label, trigger }: ActionMenuProps) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger aria-label={label} asChild>{trigger}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" className="action-menu" sideOffset={6}>
          {items.map((item) => (
            <DropdownMenu.Item
              className="action-menu__item"
              disabled={item.disabled}
              key={item.label}
              onSelect={item.onSelect}
            >
              {item.label}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
