import Link from "next/link";

interface GradientButtonProps {
  href: string;
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function GradientButton({
  href,
  children,
  variant = "primary",
  size = "md",
  className = "",
}: GradientButtonProps) {
  const sizes = {
    sm: "px-4 py-2 text-sm",
    md: "px-6 py-2.5 text-sm",
    lg: "px-8 py-3 text-base",
  };

  const variants = {
    primary:
      "bg-gradient-to-r from-brand-indigo to-brand-purple text-white hover:opacity-90 transition-opacity",
    ghost:
      "border border-slate-line text-slate-body hover:border-slate-muted hover:text-slate-heading transition-colors",
  };

  return (
    <Link
      href={href}
      className={`inline-block rounded-lg font-semibold ${sizes[size]} ${variants[variant]} ${className}`}
    >
      {children}
    </Link>
  );
}
