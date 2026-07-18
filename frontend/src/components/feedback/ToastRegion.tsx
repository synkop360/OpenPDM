import * as ToastPrimitive from "@radix-ui/react-toast";
import type { ReactNode } from "react";

type ToastRegionProps = {
  action?: ReactNode;
  description?: string;
  onOpenChange?: (open: boolean) => void;
  open: boolean;
  title: string;
};

export function ToastRegion({ action, description, onOpenChange, open, title }: ToastRegionProps) {
  return (
    <ToastPrimitive.Provider swipeDirection="right">
      <ToastPrimitive.Root className="toast" onOpenChange={onOpenChange} open={open}>
        <ToastPrimitive.Title>{title}</ToastPrimitive.Title>
        {description ? <ToastPrimitive.Description>{description}</ToastPrimitive.Description> : null}
        {action ? <ToastPrimitive.Action altText="Run notification action" asChild>{action}</ToastPrimitive.Action> : null}
        <ToastPrimitive.Close aria-label="Dismiss notification" className="toast__close">×</ToastPrimitive.Close>
      </ToastPrimitive.Root>
      <ToastPrimitive.Viewport className="toast-viewport" />
    </ToastPrimitive.Provider>
  );
}
