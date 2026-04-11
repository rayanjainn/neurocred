import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/dib/utils";

const badgeVariants = cva(
  "inline-flex items-center justify-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.1em] w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 aria-invalid:border-destructive transition-[color,box-shadow] overflow-hidden",
  {
    variants: {
      variant: {
        default:
          "border-[rgba(200,255,0,0.24)] bg-[rgba(200,255,0,0.1)] text-[#a8d900] [a&]:hover:bg-[rgba(200,255,0,0.16)]",
        secondary:
          "border-[rgba(0,240,255,0.24)] bg-[rgba(0,240,255,0.1)] text-[#00c8d4] [a&]:hover:bg-[rgba(0,240,255,0.16)]",
        destructive:
          "border-[rgba(255,0,64,0.24)] bg-[rgba(255,0,64,0.1)] text-[#e0003a] [a&]:hover:bg-[rgba(255,0,64,0.16)] focus-visible:ring-destructive/20",
        outline:
          "text-muted-foreground border-border [a&]:hover:bg-secondary [a&]:hover:text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "span";

  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
