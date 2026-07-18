import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

type DialogProps = {
  children: ReactNode;
  description: string;
  onOpenChange?: (open: boolean) => void;
  open?: boolean;
  title: string;
  trigger?: ReactNode;
};

export function Dialog({ children, description, onOpenChange, open, title, trigger }: DialogProps) {
  return (
    <DialogPrimitive.Root onOpenChange={onOpenChange} open={open}>
      {trigger ? <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger> : null}
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="dialog-overlay" />
        <DialogPrimitive.Content className="dialog-content">
          <DialogPrimitive.Title>{title}</DialogPrimitive.Title>
          <DialogPrimitive.Description>{description}</DialogPrimitive.Description>
          {children}
          <DialogPrimitive.Close asChild>
            <button className="secondary-button" type="button">Close</button>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

type ConfirmDialogProps = {
  cancelLabel?: string;
  confirmLabel: string;
  description: string;
  onConfirm: () => void;
  title: string;
  trigger: ReactNode;
};

export function ConfirmDialog({
  cancelLabel = "Cancel",
  confirmLabel,
  description,
  onConfirm,
  title,
  trigger,
}: ConfirmDialogProps) {
  return (
    <AlertDialogPrimitive.Root>
      <AlertDialogPrimitive.Trigger asChild>{trigger}</AlertDialogPrimitive.Trigger>
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Overlay className="dialog-overlay" />
        <AlertDialogPrimitive.Content className="dialog-content">
          <AlertDialogPrimitive.Title>{title}</AlertDialogPrimitive.Title>
          <AlertDialogPrimitive.Description>{description}</AlertDialogPrimitive.Description>
          <div className="dialog-actions">
            <AlertDialogPrimitive.Cancel asChild>
              <button className="secondary-button" type="button">{cancelLabel}</button>
            </AlertDialogPrimitive.Cancel>
            <AlertDialogPrimitive.Action asChild>
              <button className="danger-button" onClick={onConfirm} type="button">
                {confirmLabel}
              </button>
            </AlertDialogPrimitive.Action>
          </div>
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  );
}
