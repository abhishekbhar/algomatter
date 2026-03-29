import Image from "next/image";
import Link from "next/link";

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <Image src="/logo.svg" alt="Algomatter" width={size} height={size} />
      <span className="text-lg font-extrabold tracking-tight bg-gradient-to-br from-brand-lavender to-brand-indigo bg-clip-text text-transparent">
        algomatter
      </span>
    </Link>
  );
}
