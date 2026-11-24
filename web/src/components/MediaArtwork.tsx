import { useState } from "react";
import { Headphones } from "lucide-react";

interface Props {
  src: string;
  alt: string;
  title: string;
  className?: string;
  loading?: "eager" | "lazy";
}

/**
 * Cover image with a purple gradient fallback. Podcast art comes from publishers'
 * servers, so a broken or missing image shows the title on a gradient instead.
 */
export function MediaArtwork({ src, alt, title, className = "", loading = "lazy" }: Props) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  if (!src || failedSrc === src) {
    return (
      <div
        className={`relative flex flex-col items-center justify-center bg-gradient-to-br from-violet-900 via-purple-950 to-[#0B0514] text-[#E9D5FF]/70 select-none ${className}`}
        role="img"
        aria-label={alt}
      >
        <Headphones className="w-8 h-8 mb-2 opacity-70" aria-hidden="true" />
        <span className="font-display text-sm font-semibold tracking-tight text-center px-4 line-clamp-2 text-[#F5F1FC]">
          {title}
        </span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      loading={loading}
      referrerPolicy="no-referrer"
      onError={() => setFailedSrc(src)}
      className={className}
    />
  );
}
