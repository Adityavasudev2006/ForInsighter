export function BrandMark({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="fiGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.9" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.55" />
        </linearGradient>
      </defs>
      <rect x="6" y="6" width="52" height="52" rx="14" fill="url(#fiGrad)" opacity="0.18" />
      <path
        d="M22 44V20h22v6H29v4h12v6H29v8h-7Zm25 0V20h-7v24h7Z"
        fill="currentColor"
      />
    </svg>
  );
}

