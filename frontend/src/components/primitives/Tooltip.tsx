import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

type TooltipProps = {
  children: ReactNode;
  content: ReactNode;
};

export function Tooltip({ children, content }: TooltipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={400}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content className="tooltip-content" sideOffset={6}>
            {content}
            <TooltipPrimitive.Arrow className="tooltip-arrow" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
